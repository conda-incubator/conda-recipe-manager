"""
File:           recipe_parser.py
Description:    Provides a class that takes text from a Jinja-formatted recipe file and parses it. This allows for easy
                semantic understanding and manipulation of the file.

                Patching these files is done using a JSON-patch like syntax. This project closely conforms to the
                RFC 6902 spec, but deviates in some specific ways to handle the Jinja variables and comments found in
                conda recipe files.

                Links:
                - https://jsonpatch.com/
                - https://datatracker.ietf.org/doc/html/rfc6902/
"""
# Allows older versions of python to use newer forms of type annotation. There are major features introduced in >=3.9
from __future__ import annotations

import ast
import difflib
import json
import re
import sys
from typing import Callable, Final, Optional, TypeGuard, cast, no_type_check

import yaml
from jsonschema import validate as schema_validate

from percy.parser._node import Node
from percy.parser._selector_info import SelectorInfo
from percy.parser._traverse import (
    INVALID_IDX,
    remap_child_indices_virt_to_phys,
    traverse,
    traverse_all,
    traverse_with_index,
)
from percy.parser._types import (
    PERCY_SUB_MARKER,
    ROOT_NODE_VALUE,
    TOP_LEVEL_KEY_SORT_ORDER,
    V1_TEST_SECTION_KEY_SORT_ORDER,
    ForceIndentDumper,
    Regex,
    StrStack,
)
from percy.parser._utils import (
    dedupe_and_preserve_order,
    normalize_multiline_strings,
    num_tab_spaces,
    stack_path_to_str,
    str_to_stack_path,
    stringify_yaml,
    substitute_markers,
)
from percy.parser.enums import SelectorConflictMode
from percy.parser.exceptions import JsonPatchValidationException
from percy.parser.types import (
    CURRENT_RECIPE_SCHEMA_FORMAT,
    JSON_PATCH_SCHEMA,
    TAB_AS_SPACES,
    TAB_SPACE_COUNT,
    MessageCategory,
    MessageTable,
    MultilineVariant,
)
from percy.types import PRIMITIVES_TUPLE, JsonPatchType, JsonType, Primitives, SentinelType


class RecipeParser:
    """
    Class that parses a recipe file string. Provides many useful mechanisms for changing values in the document.

    A quick search for Jinja statements in YAML files shows that the vast majority of statements are in the form of
    initializing variables with `set`.

    The next few prevalent kinds of statements are:
      - Conditional macros (i.e. if/endif)
      - for loops
    And even those only show up in a handful out of thousands of recipes. There are also no current examples of Jinja
    style comments.

    So that being said, the initial parser will not support these more edge-case recipes as they don't pass the 80/20
    rule.
    """

    # Static set of patch operations that require `from`. The others require `value` or nothing.
    _patch_ops_requiring_from = set(["copy", "move"])
    # Sentinel object used for detecting defaulting behavior.
    # See here for a good explanation: https://peps.python.org/pep-0661/
    _sentinel = SentinelType()

    @staticmethod
    def _parse_yaml(s: str, parser: Optional[RecipeParser] = None) -> JsonType:
        """
        Parse a line (or multiple) of YAML into a Pythonic data structure
        :param s: String to parse
        :param parser: (Optional) If provided, this will substitute Jinja variables with values specified in in the
            recipe file. Since `_parse_yaml()` is critical to constructing recipe files, this function must remain
            static. Also, during construction, we shouldn't be using a variables until the entire recipe is read/parsed.
        :returns: Pythonic data corresponding to the line of YAML
        """

        # Recursive helper function used when we need to perform variable substitutions
        def _parse_yaml_recursive_sub(data: JsonType, modifier: Callable[[str], JsonType]) -> JsonType:
            # Add the substitutions back in
            if isinstance(data, str):
                data = modifier(data)
            if isinstance(data, dict):
                for key in data.keys():
                    data[key] = _parse_yaml_recursive_sub(cast(str, data[key]), modifier)
            elif isinstance(data, list):
                for i in range(len(data)):
                    data[i] = _parse_yaml_recursive_sub(cast(str, data[i]), modifier)
            return data

        output: JsonType = None
        try:
            output = cast(JsonType, yaml.safe_load(s))
        except Exception:  # pylint: disable=broad-exception-caught
            # If a construction exception is thrown, attempt to re-parse by replacing Jinja macros (substrings in
            # `{{}}`) with friendly string substitution markers, then re-inject the substitutions back in. We classify
            # all Jinja substitutions as string values, so we don't have to worry about the type of the actual
            # substitution.
            sub_list: list[str] = Regex.JINJA_SUB.findall(s)
            s = Regex.JINJA_SUB.sub(PERCY_SUB_MARKER, s)
            output = _parse_yaml_recursive_sub(
                cast(JsonType, yaml.safe_load(s)), lambda d: substitute_markers(d, sub_list)
            )
            # Because we leverage PyYaml to parse the data structures, we need to perform a second pass to perform
            # variable substitutions.
            if parser is not None:
                output = _parse_yaml_recursive_sub(
                    output, parser._render_jinja_vars  # pylint: disable=protected-access
                )
        return output

    @staticmethod
    def _parse_line_node(s: str) -> Node:
        """
        Parses a line of conda-formatted YAML into a Node.

        Latest YAML spec can be found here: https://yaml.org/spec/1.2.2/

        :param s: Pre-stripped (no leading/trailing spaces), non-Jinja line of a recipe file
        :returns: A Node representing a line of the conda-formatted YAML.
        """
        # Use PyYaml to safely/easily/correctly parse single lines of YAML.
        output = RecipeParser._parse_yaml(s)

        # Attempt to parse-out comments. Fully commented lines are not ignored to preserve context when the text is
        # rendered. Their order in the list of child nodes will preserve their location. Fully commented lines just have
        # a value of "None".
        #
        # There is an open issue to PyYaml to support comment parsing:
        #   - https://github.com/yaml/pyyaml/issues/90
        comment = ""
        # The full line is a comment
        if s.startswith("#"):
            return Node(comment=s)
        # There is a comment at the end of the line if a `#` symbol is found with leading whitespace before it. If it is
        # "touching" a character on the left-side, it is just part of a string.
        comment_re_result = Regex.DETECT_TRAILING_COMMENT.search(s)
        if comment_re_result is not None:
            # Group 0 is the whole match, Group 1 is the leading whitespace, Group 2 locates the `#`
            comment = s[comment_re_result.start(2) :]

        # If a dictionary is returned, we have a line containing a key and potentially a value. There should only be 1
        # key/value pairing in 1 line. Nodes representing keys should be flagged for handling edge cases.
        if isinstance(output, dict):
            children: list[Node] = []
            key = list(output.keys())[0]
            # If the value returned is None, there is no leaf node to set
            if output[key] is not None:
                # As the line is shared by both parent and child, the comment gets tagged to both.
                children.append(Node(cast(Primitives, output[key]), comment))
            return Node(key, comment, children, key_flag=True)
        # If a list is returned, then this line is a listed member of the parent Node
        if isinstance(output, list):
            # The full line is a comment
            if s.startswith("#"):
                # Comments are list members to ensure indentation
                return Node(comment=comment, list_member_flag=True)
            # Special scenarios that can occur on 1 line:
            #   1. Lists can contain lists: - - foo -> [["foo"]]
            #   2. Lists can contain keys:  - foo: bar -> [{"foo": "bar"}]
            # And, of course, there can be n values in each of these collections on 1 line as well. Scenario 2 occurs in
            # multi-output recipe files so we need to support the scenario here.
            #
            # `PKG-3006` tracks an investigation effort into what we need to support for our purposes.
            if isinstance(output[0], dict):
                # Build up the key-and-potentially-value pair nodes first
                key_children: list[Node] = []
                key = list(output[0].keys())[0]
                if output[0][key] is not None:
                    key_children.append(Node(cast(Primitives, output[0][key]), comment))
                key_node = Node(key, comment, key_children, key_flag=True)

                elem_node = Node(comment=comment, list_member_flag=True)
                elem_node.children.append(key_node)
                return elem_node
            return Node(cast(Primitives, output[0]), comment, list_member_flag=True)
        # Other types are just leaf nodes. This is scenario should likely not be triggered given our recipe files don't
        # have single valid lines of YAML, but we cover this case for the sake of correctness.
        return Node(output, comment)

    @staticmethod
    def _generate_subtree(value: JsonType) -> list[Node]:
        """
        Given a value supported by JSON, use the RecipeParser to generate a list of child nodes. This effectively
        creates a new subtree that can be used to patch other parse trees.
        """
        # Multiline values can replace the list of children with a single multiline leaf node.
        if isinstance(value, str) and "\n" in value:
            return [
                Node(
                    value=value.splitlines(),
                    # The conversion from JSON-to-YAML is lossy here. Default to the closest equivalent, which preserves
                    # newlines.
                    multiline_variant=MultilineVariant.PIPE,
                )
            ]

        # For complex types, generate the YAML equivalent and build a new tree.
        if not isinstance(value, PRIMITIVES_TUPLE):
            # Although not technically required by YAML, we add the optional spacing for human readability.
            return RecipeParser(  # pylint: disable=protected-access
                yaml.dump(value, Dumper=ForceIndentDumper)  # type: ignore[misc]
            )._root.children

        # Primitives can be safely stringified to generate a parse tree.
        return RecipeParser(str(stringify_yaml(value)))._root.children  # pylint: disable=protected-access

    def _render_jinja_vars(self, s: str) -> JsonType:
        """
        Helper function that replaces Jinja substitutions with their actual set values.
        :param s: String to be re-rendered
        :returns: The original value, augmented with Jinja substitutions. Types are re-rendered to account for multiline
            strings that may have been "normalized" prior to this call.
        """
        # Search the string, replacing all substitutions we can recognize
        for match in cast(list[str], Regex.JINJA_SUB.findall(s)):
            lower_case = False
            # The regex guarantees the string starts and ends with double braces
            key = match[2:-2].strip()
            # A brief search through `aggregate` shows that `|lower` is a commonly used Jinja command. Few, if any,
            # other commands are used, as of writing. If others are found, we might need to support them here.
            lower_match = Regex.JINJA_FUNCTION_LOWER.search(key)
            if lower_match is not None:
                lower_case = True
                key = key.replace(lower_match.group(), "").strip()

            if key in self._vars_tbl:
                # Replace value as a string. Re-interpret the entire value before returning.
                value = str(self._vars_tbl[key])
                if lower_case:
                    value = value.lower()
                s = s.replace(match, value)
        return cast(JsonType, yaml.safe_load(s))

    def _rebuild_selectors(self) -> None:
        """
        Re-builds the selector look-up table. This table allows quick access to tree nodes that have a selector
        specified. This needs to be called when the tree or selectors are modified.
        """
        self._selector_tbl: dict[str, list[SelectorInfo]] = {}

        def _collect_selectors(node: Node, path: StrStack) -> None:
            # Ignore empty comments
            if not node.comment:
                return
            match = Regex.SELECTOR.search(node.comment)
            if match:
                selector = match.group(0)
                selector_info = SelectorInfo(node, list(path))
                if selector not in self._selector_tbl:
                    self._selector_tbl[selector] = [selector_info]
                else:
                    self._selector_tbl[selector].append(selector_info)

        traverse_all(self._root, _collect_selectors)

    def __init__(self, content: str):
        """
        Constructs a RecipeParser instance.
        :param content: conda-build formatted recipe file, as a single text string.
        """
        # The initial, raw, text is preserved for diffing and debugging purposes
        self._init_content: Final[str] = content
        # Indicates if the original content has changed
        self._is_modified = False

        # Tracks Jinja variables set by the file
        self._vars_tbl: dict[str, JsonType] = {}
        # Find all the set statements and record the values
        for line in cast(list[str], Regex.JINJA_SET_LINE.findall(self._init_content)):
            key = line[line.find("set") + len("set") : line.find("=")].strip()
            value = line[line.find("=") + len("=") : line.find("%}")].strip()
            try:
                self._vars_tbl[key] = ast.literal_eval(value)  # type: ignore[misc]
            except Exception:  # pylint: disable=broad-exception-caught
                self._vars_tbl[key] = value

        # Root of the parse tree
        self._root = Node(ROOT_NODE_VALUE)
        # Start by removing all Jinja lines. Then traverse line-by-line
        sanitized_yaml = Regex.JINJA_LINE.sub("", self._init_content)

        # Read the YAML line-by-line, maintaining a stack to manage the last owning node in the tree.
        node_stack: list[Node] = [self._root]
        # Relative depth is determined by the increase/decrease of indentation marks (spaces)
        cur_indent = 0
        last_node = node_stack[-1]

        # Iterate with an index variable, so we can handle multiline values
        line_idx = 0
        lines = sanitized_yaml.splitlines()
        num_lines = len(lines)
        while line_idx < num_lines:
            line = lines[line_idx]
            # Increment here, so that the inner multiline processing loop doesn't cause a skip of the line following the
            # multiline value.
            line_idx += 1
            # Ignore empty lines
            clean_line = line.strip()
            if clean_line == "":
                continue

            new_indent = num_tab_spaces(line)
            new_node = RecipeParser._parse_line_node(clean_line)
            # If the last node ended (pre-comments) with a |, reset the value to be a list of the following,
            # extra-indented strings
            multiline_re_match = Regex.MULTILINE.match(line)
            if multiline_re_match:
                # Calculate which multiline symbol is used. The first character must be matched, the second is optional.
                variant_capture = cast(str, multiline_re_match.group(Regex.MULTILINE_VARIANT_CAPTURE_GROUP_CHAR))
                variant_sign = cast(str | None, multiline_re_match.group(Regex.MULTILINE_VARIANT_CAPTURE_GROUP_SUFFIX))
                if variant_sign is not None:
                    variant_capture += variant_sign
                # Per YAML spec, multiline statements can't be commented. In other words, the `#` symbol is seen as a
                # string character in multiline values.
                multiline_node = Node(
                    [],
                    multiline_variant=MultilineVariant(variant_capture),
                )
                # Type narrow that we assigned `value` as a `list`
                assert isinstance(multiline_node.value, list)
                multiline = lines[line_idx]
                multiline_indent = num_tab_spaces(multiline)
                # Add the line to the list once it is verified to be the next line to capture in this node. This means
                # that `line_idx` will point to the line of the next node, post-processing. Note that blank lines are
                # valid in multi-line strings, occasionally found in `/about/summary` sections.
                while multiline_indent > new_indent or multiline == "":
                    multiline_node.value.append(multiline.strip())
                    line_idx += 1
                    multiline = lines[line_idx]
                    multiline_indent = num_tab_spaces(multiline)
                # The previous level is the key to this multi-line value, so we can safely reset it.
                new_node.children = [multiline_node]
            if new_indent > cur_indent:
                node_stack.append(last_node)
            elif new_indent < cur_indent:
                # Multiple levels of depth can change from line to line, so multiple stack nodes must be pop'd. Example:
                # foo:
                #   bar:
                #     fizz: buzz
                # baz: blah
                # TODO Figure out tab-depth of the recipe being read. 4 spaces is technically valid in YAML
                depth_to_pop = (cur_indent - new_indent) // TAB_SPACE_COUNT
                for _ in range(depth_to_pop):
                    node_stack.pop()
            cur_indent = new_indent
            # Look at the stack to determine the parent Node and then append the current node to the new parent.
            parent = node_stack[-1]
            parent.children.append(new_node)
            # Update the last node for the next line interpretation
            last_node = new_node

        # Now that the tree is built, construct a selector look-up table that tracks all the nodes that use a particular
        # selector. This will make it easier to.
        #
        # This table will have to be re-built or modified when the tree is modified with `patch()`.
        self._rebuild_selectors()

    @staticmethod
    def _canonical_sort_keys_comparison(n: Node, priority_tbl: dict[str, int]) -> int:
        """
        Given a look-up table defining "canonical" sort order, this function provides a way to compare Nodes.
        :param n: Node to evaluate
        :param priority_tbl: Table that provides a "canonical ordering" of keys
        :returns: An integer indicating sort-order priority
        """
        # For now, put all comments at the top of the section. Arguably this is better than having them "randomly tag"
        # to another top-level key.
        if n.is_comment():
            return -sys.maxsize
        # Unidentified keys go to the bottom of the section.
        if not isinstance(n.value, str) or n.value not in priority_tbl:
            return sys.maxsize
        return priority_tbl[n.value]

    @staticmethod
    def _str_tree_recurse(node: Node, depth: int, lines: list[str]) -> None:
        """
        Helper function that renders a parse tree as a text-based dependency tree. Useful for debugging.
        :param node: Node of interest
        :param depth: Current depth of the node
        :param lines: Accumulated list of lines to text to render
        """
        spaces = TAB_AS_SPACES * depth
        branch = "" if depth == 0 else "|- "
        lines.append(f"{spaces}{branch}{node.short_str()}")
        for child in node.children:
            RecipeParser._str_tree_recurse(child, depth + 1, lines)

    def __str__(self) -> str:
        """
        Casts the parser into a string. Useful for debugging.
        :returns: String representation of the recipe file
        """
        s = "--------------------\n"
        tree_lines: list[str] = []
        RecipeParser._str_tree_recurse(self._root, 0, tree_lines)
        s += "RecipeParser Instance\n"
        s += "- Variables Table:\n"
        s += json.dumps(self._vars_tbl, indent=TAB_AS_SPACES) + "\n"
        s += "- Selectors Table:\n"
        for key, val in self._selector_tbl.items():
            s += f"{TAB_AS_SPACES}{key}\n"
            for info in val:
                s += f"{TAB_AS_SPACES}{TAB_AS_SPACES}- {info}\n"
        s += f"- is_modified?: {self._is_modified}\n"
        s += "- Tree:\n" + "\n".join(tree_lines) + "\n"
        s += "--------------------\n"

        return s

    def __eq__(self, other: object) -> bool:
        """
        Checks if two recipe representations match entirely
        :param other: Other recipe parser instance to check against.
        :returns: True if both recipes contain the same current state. False otherwise.
        """
        if not isinstance(other, RecipeParser):
            raise TypeError
        return self.render() == other.render()

    def is_modified(self) -> bool:
        """
        Indicates if the recipe has been changed since construction.
        :returns: True if the recipe has changed. False otherwise.
        """
        return self._is_modified

    def has_unsupported_statements(self) -> bool:
        """
        Runs a series of checks against the original recipe file.
        :returns: True if the recipe has statements we do not currently support. False otherwise.
        """
        # TODO complete
        raise NotImplementedError

    @staticmethod
    def _render_tree(node: Node, depth: int, lines: list[str], parent: Optional[Node] = None) -> None:
        """
        Recursive helper function that traverses the parse tree to generate a file.
        :param node: Current node in the tree
        :param depth: Current depth of the recursion
        :param lines: Accumulated list of lines in the recipe file
        :param parent: (Optional) Parent node to the current node. Set by recursive calls only.
        """
        spaces = TAB_AS_SPACES * depth

        # Edge case: The first element of dictionary in a list has a list `- ` prefix. Subsequent keys in the dictionary
        # just have a tab.
        is_first_collection_child: Final[bool] = (
            parent is not None and parent.is_collection_element() and node == parent.children[0]
        )

        # Handle same-line printing
        if node.is_single_key():
            # Edge case: Handle a list containing 1 member
            if node.children[0].list_member_flag:
                lines.append(f"{spaces}{node.value}:  {node.comment}".rstrip())
                lines.append(
                    f"{spaces}{TAB_AS_SPACES}- "
                    f"{stringify_yaml(node.children[0].value, multiline_variant=node.children[0].multiline_variant)}  "
                    f"{node.children[0].comment}".rstrip()
                )
                return

            if is_first_collection_child:
                lines.append(
                    f"{TAB_AS_SPACES * (depth-1)}- {node.value}: "
                    f"{stringify_yaml(node.children[0].value)}  "
                    f"{node.children[0].comment}".rstrip()
                )
                return

            # Handle multi-line statements. In theory this will probably only ever be strings, but we'll try to account
            # for other types.
            #
            # By the language spec, # symbols do not indicate comments on multiline strings.
            if node.children[0].multiline_variant != MultilineVariant.NONE:
                multi_variant: Final[MultilineVariant] = node.children[0].multiline_variant
                lines.append(f"{spaces}{node.value}: {multi_variant}  {node.comment}".rstrip())
                for val_line in cast(list[str], node.children[0].value):
                    lines.append(
                        f"{spaces}{TAB_AS_SPACES}"
                        f"{stringify_yaml(val_line, multiline_variant=multi_variant)}".rstrip()
                    )
                return
            lines.append(
                f"{spaces}{node.value}: "
                f"{stringify_yaml(node.children[0].value)}  "
                f"{node.children[0].comment}".rstrip()
            )
            return

        depth_delta = 1
        # Don't render a `:` for the non-visible root node. Also don't render invisible collection nodes.
        if depth > -1 and not node.is_collection_element():
            list_prefix = ""
            # Handle special cases for the "parent" key
            if node.list_member_flag:
                list_prefix = "- "
                depth_delta += 1
            if is_first_collection_child:
                list_prefix = "- "
                spaces = spaces[TAB_SPACE_COUNT:]
            # Nodes representing collections in a list have nothing to render
            lines.append(f"{spaces}{list_prefix}{node.value}:  {node.comment}".rstrip())

        for child in node.children:
            # Top-level empty-key edge case: Top level keys should have no additional indentation.
            extra_tab = "" if depth < 0 else TAB_AS_SPACES
            # Comments in a list are indented to list-level, but do not include a list `-` mark
            if child.is_comment():
                lines.append(f"{spaces}{extra_tab}" f"{child.comment}".rstrip())
            # Empty keys can be easily confused for leaf nodes. The difference is these nodes render with a "dangling"
            # `:` mark
            elif child.is_empty_key():
                lines.append(f"{spaces}{extra_tab}" f"{stringify_yaml(child.value)}:  " f"{child.comment}".rstrip())
            # Leaf nodes are rendered as members in a list
            elif child.is_leaf():
                lines.append(f"{spaces}{extra_tab}- " f"{stringify_yaml(child.value)}  " f"{child.comment}".rstrip())
            else:
                RecipeParser._render_tree(child, depth + depth_delta, lines, node)
            # By tradition, recipes have a blank line after every top-level section, unless they are a comment. Comments
            # should be left where they are.
            if depth < 0 and not child.is_comment():
                lines.append("")

    def render(self) -> str:
        """
        Takes the current state of the parse tree and returns the recipe file as a string.
        :returns: String representation of the recipe file
        """
        lines: list[str] = []

        # Render variable set section
        for key, val in self._vars_tbl.items():
            # Double quote strings
            if isinstance(val, str):
                val = f'"{val}"'
            lines.append(f"{{% set {key} = {val} %}}")
        # Add spacing if variables have been set
        if len(self._vars_tbl):
            lines.append("")

        # Render parse-tree, -1 is passed in as the "root-level" is not directly rendered in a YAML file; it is merely
        # implied.
        RecipeParser._render_tree(self._root, -1, lines)

        return "\n".join(lines)

    @no_type_check
    def _render_object_tree(self, node: Node, replace_variables: bool, data: JsonType) -> None:
        """
        Recursive helper function that traverses the parse tree to generate a Pythonic data object.
        :param node: Current node in the tree
        :param replace_variables: If set to True, this replaces all variable substitutions with their set values.
        :param data: Accumulated data structure
        """
        # Ignore comment-only lines
        if node.is_comment():
            return

        key = cast(str, node.value)
        for child in node.children:
            # Ignore comment-only lines
            if child.is_comment():
                continue

            # Handle multiline strings and variable replacement
            value = normalize_multiline_strings(child.value, child.multiline_variant)
            if isinstance(value, str):
                if replace_variables:
                    value = self._render_jinja_vars(value)
                elif child.multiline_variant != MultilineVariant.NONE:
                    value = cast(str, yaml.safe_load(value))

            # Empty keys are interpreted to point to `None`
            if child.is_empty_key():
                data[key][child.value] = None
                continue

            # Collection nodes are skipped as they are placeholders. However, their children are rendered recursively
            # and added to a list.
            if child.is_collection_element():
                elem_dict = {}
                for element in child.children:
                    self._render_object_tree(element, replace_variables, elem_dict)
                if len(data[key]) == 0:
                    data[key] = []
                data[key].append(elem_dict)
                continue

            # List members accumulate values in a list
            if child.list_member_flag:
                if key not in data:
                    data[key] = []
                data[key].append(value)
                continue

            # Other (non list and non-empty-key) leaf nodes set values directly
            if child.is_leaf():
                data[key] = value
                continue

            # All other keys prep for containing more dictionaries
            data.setdefault(key, {})
            self._render_object_tree(child, replace_variables, data[key])

    def render_to_object(self, replace_variables: bool = False) -> JsonType:
        """
        Takes the underlying state of the parse tree and produces a Pythonic object/dictionary representation. Analogous
        to `json.load()`.
        :param replace_variables: (Optional) If set to True, this replaces all variable substitutions with their set
            values.
        :returns: Pythonic data object representation of the recipe.
        """
        data: JsonType = {}
        # Type narrow after assignment
        assert isinstance(data, dict)

        # Bootstrap/flatten the root-level
        for child in self._root.children:
            if child.is_comment():
                continue
            data.setdefault(cast(str, child.value), {})
            self._render_object_tree(child, replace_variables, data)

        return data

    def render_to_new_recipe_format(self) -> tuple[str, MessageTable]:
        # pylint: disable=protected-access
        """
        Takes the current recipe representation and renders it to the new format WITHOUT modifying the current recipe
        state.

        The "new" format is defined in the following CEPs:
          - https://github.com/conda-incubator/ceps/blob/main/cep-13.md
          - https://github.com/conda-incubator/ceps/blob/main/cep-14.md

        (As of writing there is no official name other than "the new recipe format")
        """
        # Approach: In the event that we want to expand support later, this function should be implemented in terms
        # of a `RecipeParser` tree. This will make it easier to build an upgrade-path, if we so choose to pursue one.

        msg_tbl = MessageTable()

        # `copy.deepcopy()` produced some bizarre artifacts, namely single-line comments were being incorrectly rendered
        # as list members. Although inefficient, we have tests that validate round-tripping the parser and there
        # is no development cost in utilizing tools we already must maintain.
        new_recipe: RecipeParser = RecipeParser(self.render())
        # Log the original
        old_comments: Final[dict[str, str]] = new_recipe.get_comments_table()

        # Convenience wrapper that logs failed patches to the message table
        def _patch_and_log(patch: JsonPatchType) -> None:
            if not new_recipe.patch(patch):
                msg_tbl.add_message(MessageCategory.ERROR, f"Failed to patch: {patch}")

        # Convenience function constructs missing paths. Useful when you have to construct more than 1 path level at
        # once (the JSON patch standard only allows the creation of 1 new level at a time)
        def _patch_add_missing_path(base_path: str, ext: str, value: JsonType = None) -> None:
            temp_path: Final[str] = RecipeParser.append_to_path(base_path, ext)
            if new_recipe.contains_value(temp_path):
                return
            _patch_and_log({"op": "add", "path": temp_path, "value": value})

        # Convenience function that moves a value under an old path to a new one sharing a common base path BUT only if
        # the old path exists.
        def _patch_move_base_path(base_path: str, old_ext: str, new_ext: str) -> None:
            old_path: Final[str] = RecipeParser.append_to_path(base_path, old_ext)
            if not new_recipe.contains_value(old_path):
                return
            _patch_and_log({"op": "move", "from": old_path, "path": RecipeParser.append_to_path(base_path, new_ext)})

        # Convenience function that sorts 1 level of keys, given a path. Optionally allows renaming of the target node.
        def _sort_subtree_keys(sort_path: str, tbl: dict[str, int], rename: str = "") -> None:
            def _comparison(n: Node) -> int:
                return RecipeParser._canonical_sort_keys_comparison(n, tbl)

            node = traverse(new_recipe._root, str_to_stack_path(sort_path))
            if node is None:
                msg_tbl.add_message(MessageCategory.WARNING, f"Failed to sort members of {sort_path}")
                return
            if rename:
                node.value = rename
            node.children.sort(key=_comparison)

        # Convert the JINJA variable table to a `context` section. Empty tables still add the `context` section for
        # future developers' convenience.
        _patch_and_log({"op": "add", "path": "/context", "value": None})
        # Filter-out any value not covered in the new format
        for name, value in new_recipe._vars_tbl.items():
            if not isinstance(value, (str, int, float, bool)):
                msg_tbl.add_message(MessageCategory.WARNING, f"The variable `{name}` is an unsupported type.")
                continue
            _patch_and_log({"op": "add", "path": f"/context/{name}", "value": value})

        # Similarly, patch-in the new `schema_version` value to the top of the file
        _patch_and_log({"op": "add", "path": "/schema_version", "value": CURRENT_RECIPE_SCHEMA_FORMAT})

        # Swap all JINJA to use the new `${{ }}` format.
        jinja_sub_locations: Final[list[str]] = new_recipe.search(Regex.JINJA_SUB)
        for path in jinja_sub_locations:
            value = new_recipe.get_value(path)
            # Values that match the regex should only be strings. This prevents crashes that should not occur.
            if not isinstance(value, str):
                msg_tbl.add_message(
                    MessageCategory.WARNING, f"A non-string value was found as a JINJA substitution: {value}"
                )
                continue
            value = value.replace("{{", "${{")
            _patch_and_log({"op": "replace", "path": path, "value": value})

        # Convert selectors into ternary statements or `if` blocks
        for selector, instances in new_recipe._selector_tbl.items():
            for info in instances:
                # Selectors can be applied to the parent node if they appear on the same line. We'll ignore these when
                # building replacements.
                if not info.node.is_leaf():
                    continue

                # Strip the []'s around the selector
                bool_expression = selector[1:-1]
                # Convert to a public-facing path representation
                selector_path = stack_path_to_str(info.path)

                # For now, if a selector lands on a boolean value, use a ternary statement. Otherwise use the
                # conditional logic.
                # TODO `skip` is special and now can be a list of boolean expressions.
                patch: JsonPatchType = {
                    "op": "replace",
                    "path": selector_path,
                    "value": "${{ true if " + bool_expression + " }}",
                }
                if not isinstance(info.node.value, bool):
                    # TODO: This logic from CEP-13 may be mis-guided
                    # CEP-13 states that ONLY list members may use the `if/then/else` blocks
                    if not info.node.list_member_flag:
                        msg_tbl.add_message(
                            MessageCategory.WARNING, f"A non-list item had a selector at: {selector_path}"
                        )
                        continue
                    bool_object = {
                        "if": bool_expression,
                        "then": None if isinstance(info.node.value, SentinelType) else info.node.value,
                    }
                    patch = {
                        "op": "replace",
                        "path": selector_path,
                        # Hack: Surround the patched value in a list to render as a list member.
                        # TODO: Figure out if this is a bug in the patch code.
                        "value": cast(JsonType, [bool_object]),
                    }
                # Apply the patch
                _patch_and_log(patch)
                new_recipe.remove_selector(selector_path)

        # TODO Complete
        # Scan and alert removed fields
        # build/
        # about/

        # Move `run_exports` and `ignore_run_exports` from `build` to `requirements`
        # TODO Fix: comments are not preserved with patch operations (add a flag to `patch()`?)
        for base_path in new_recipe.get_package_paths():
            # `run_exports`
            old_re_path = RecipeParser.append_to_path(base_path, "/build/run_exports")
            if new_recipe.contains_value(old_re_path):
                requirements_path = RecipeParser.append_to_path(base_path, "/requirements")
                new_re_path = RecipeParser.append_to_path(base_path, "/requirements/run_exports")
                if not new_recipe.contains_value(requirements_path):
                    _patch_and_log({"op": "add", "path": requirements_path, "value": None})
                _patch_and_log({"op": "move", "from": old_re_path, "path": new_re_path})

            # `ignore_run_exports`
            old_ire_path = RecipeParser.append_to_path(base_path, "/build/ignore_run_exports")
            if new_recipe.contains_value(old_re_path):
                requirements_path = RecipeParser.append_to_path(base_path, "/requirements")
                new_ire_path = RecipeParser.append_to_path(base_path, "/requirements/ignore_run_exports")
                if not new_recipe.contains_value(requirements_path):
                    _patch_and_log({"op": "add", "path": requirements_path, "value": None})
                _patch_and_log({"op": "move", "from": old_ire_path, "path": new_ire_path})

        ## `about` section changes and validation ##
        # Warn if "required" fields are missing
        about_required: Final[list[str]] = [
            "summary",
            "description",
            "license",
            "license_file",
            "license_url",
        ]
        for field in about_required:
            path = f"/about/{field}"
            if not new_recipe.contains_value(path):
                msg_tbl.add_message(MessageCategory.WARNING, f"Required field missing: {path}")

        # Transform renamed fields
        about_rename: Final[list[tuple[str, str]]] = [
            ("home", "homepage"),
            ("dev_url", "repository"),
            ("doc_url", "documentation"),
        ]
        for old, new in about_rename:
            _patch_move_base_path("/about", old, new)

        # TODO validate: /about/license must be SPDX recognized.

        # Remove deprecated `about` fields
        about_deprecated: Final[list[str]] = [
            "prelink_message",
            "license_family",
            "identifiers",
            "tags",
            "keywords",
            "doc_source_url",
        ]
        for field in about_deprecated:
            path = f"/about/{field}"
            if new_recipe.contains_value(path):
                _patch_and_log({"op": "remove", "path": path})

        # Cached copy of all of the "outputs" in a recipe. This is useful for easily handling multi and single output
        # recipes in 1 loop construct.
        base_package_paths: Final[list[str]] = new_recipe.get_package_paths()

        ## Upgrade the testing section(s) ##
        test_paths: Final[map[str]] = map(
            cast(Callable[[str], str], lambda s: RecipeParser.append_to_path(s, "/test")), base_package_paths
        )
        for test_path in test_paths:
            if not new_recipe.contains_value(test_path):
                continue

            _patch_move_base_path(test_path, "/files", "/files/recipe")
            # Edge case: `/source_files` exists but `/files` does not
            if new_recipe.contains_value(RecipeParser.append_to_path(test_path, "/source_files")):
                _patch_add_missing_path(test_path, "/files")
            _patch_move_base_path(test_path, "/source_files", "/files/source")

            if new_recipe.contains_value(RecipeParser.append_to_path(test_path, "/requires")):
                _patch_add_missing_path(test_path, "/requirements")
            _patch_move_base_path(test_path, "/requires", "/requirements/run")

            # Replace `- pip check` in `commands` with the new flag. If not found, set the flag to `False` (as the
            # flag defaults to `True`).
            commands = cast(list[str], new_recipe.get_value(RecipeParser.append_to_path(test_path, "/commands"), []))
            pip_check = False
            for i, command in enumerate(commands):
                if command != "pip check":
                    continue
                # For now, we will only patch-out the first instance when no selector is attached
                # TODO Future: handle selector logic/cases with `pip check || <bool>`
                _patch_and_log({"op": "remove", "path": RecipeParser.append_to_path(test_path, f"/commands/{i}")})
                pip_check = True
                break
            _patch_add_missing_path(test_path, "/python")
            _patch_and_log(
                {"op": "add", "path": RecipeParser.append_to_path(test_path, "/python/pip-check"), "value": pip_check}
            )

            _patch_move_base_path(test_path, "/commands", "/script")
            _patch_move_base_path(test_path, "/imports", "/python/imports")
            _patch_move_base_path(test_path, "/downstreams", "/downstream")

            # Sort test section for "canonical order" and rename `test` to `tests`. This effectively invalidates
            # the `test_path` variable from this point on.
            _sort_subtree_keys(test_path, V1_TEST_SECTION_KEY_SORT_ORDER, rename="tests")

        ## Upgrade the multi-output section(s) ##
        # TODO Complete
        if new_recipe.contains_value("/outputs"):
            # On the top-level, `package` -> `recipe`
            _patch_move_base_path(ROOT_NODE_VALUE, "/package", "/recipe")

            for output_path in base_package_paths:
                if output_path == ROOT_NODE_VALUE:
                    continue

                # Move `name` and `version` under `package`
                if new_recipe.contains_value(
                    RecipeParser.append_to_path(output_path, "/name")
                ) or new_recipe.contains_value(RecipeParser.append_to_path(output_path, "/version")):
                    _patch_add_missing_path(output_path, "/package")
                _patch_move_base_path(output_path, "/name", "/package/name")
                _patch_move_base_path(output_path, "/version", "/package/version")

                # Not all the top-level keys are found in each output section, but all the output section keys are
                # found at the top-level. So for consistency, we sort on that ordering.
                _sort_subtree_keys(output_path, TOP_LEVEL_KEY_SORT_ORDER)

        ## Final clean-up ##

        # TODO: Comment tracking may need improvement. The "correct way" of tracking comments with patch changes is a
        #       fairly big engineering effort and refactor.
        # Alert the user which comments have been dropped.
        new_comments: Final[dict[str, str]] = new_recipe.get_comments_table()
        diff_comments: Final[dict[str, str]] = {k: v for k, v in old_comments.items() if k not in new_comments}
        for path, comment in diff_comments.items():
            if not new_recipe.contains_value(path):
                msg_tbl.add_message(MessageCategory.WARNING, f"Could not relocate comment: {comment}")

        # TODO Complete: move operations may result in empty fields we can eliminate. This may require changes to
        #                `contains_value()`
        # TODO Complete: Attempt to combine consecutive If/Then blocks after other modifications. This should reduce the
        #                risk of screwing up critical list indices and ordering.

        # Hack: Wipe the existing table so the JINJA `set` statements don't render the final form
        new_recipe._vars_tbl = {}

        # Sort the top-level keys to a "canonical" ordering. This should make previous patch operations look more
        # "sensible" to a human reader.
        _sort_subtree_keys("/", TOP_LEVEL_KEY_SORT_ORDER)

        return new_recipe.render(), msg_tbl

    ## YAML Access Functions ##

    def list_value_paths(self) -> list[str]:
        """
        Provides a list of all known terminal paths. This can be used by the caller to perform search operations.
        :returns: List of all terminal paths in the parse tree.
        """
        lst: list[str] = []

        def _find_paths(node: Node, path_stack: StrStack) -> None:
            if node.is_leaf():
                lst.append(stack_path_to_str(path_stack))

        traverse_all(self._root, _find_paths)
        return lst

    def contains_value(self, path: str) -> bool:
        """
        Determines if a value (via a path) is contained in this recipe. This also allows the caller to determine if a
        path exists.
        :param path: JSON patch (RFC 6902)-style path to a value.
        :returns: True if the path exists. False otherwise.
        """
        path_stack = str_to_stack_path(path)
        return traverse(self._root, path_stack) is not None

    def get_value(self, path: str, default: JsonType | SentinelType = _sentinel, sub_vars: bool = False) -> JsonType:
        """
        Retrieves a value at a given path. If the value is not found, return a specified default value or throw.
        :param path: JSON patch (RFC 6902)-style path to a value.
        :param default: (Optional) If the value is not found, return this value instead.
        :param sub_vars: (Optional) If set to True and the value contains a Jinja template variable, the Jinja value
            will be "rendered".
        :raises KeyError: If the value is not found AND no default is specified
        :returns: If found, the value in the recipe at that path. Otherwise, the caller-specified default value.
        """
        path_stack = str_to_stack_path(path)
        node = traverse(self._root, path_stack)

        # Handle if the path was not found
        if node is None:
            if default == RecipeParser._sentinel or isinstance(default, SentinelType):
                raise KeyError(f"No value/key found at path {path!r}")
            return default

        return_value: JsonType = None
        # Handle unpacking of the last key-value set of nodes.
        if node.is_single_key() and not node.is_root():
            # As of writing, Jinja substitutions are not used
            if node.children[0].multiline_variant != MultilineVariant.NONE:
                multiline_str = cast(
                    str,
                    normalize_multiline_strings(
                        cast(list[str], node.children[0].value), node.children[0].multiline_variant
                    ),
                )
                if sub_vars:
                    return self._render_jinja_vars(multiline_str)
                return cast(JsonType, yaml.safe_load(multiline_str))
            return_value = cast(Primitives, node.children[0].value)
        # Leaf nodes can return their value directly
        elif node.is_leaf():
            return_value = cast(Primitives, node.value)
        else:
            # NOTE: Traversing the tree and generating our own data structures will be more efficient than rendering and
            # leveraging the YAML parser, BUT this method re-uses code and is easier to maintain.
            lst: list[str] = []
            RecipeParser._render_tree(node, -1, lst)
            return_value = "\n".join(lst)

        # Collection types are transformed into strings above and will need to be transformed into a proper data type.
        # `_parse_yaml()` will also render JINJA variables for us, if requested.
        if isinstance(return_value, str):
            parser = self if sub_vars else None
            parsed_value = RecipeParser._parse_yaml(return_value, parser)
            # Lists containing 1 value will drop the surrounding list by the YAML parser. To ensure greater consistency
            # and provide better type-safety, we will re-wrap such values.
            if len(node.children) == 1 and node.children[0].list_member_flag:
                return [parsed_value]
            return parsed_value
        return return_value

    def find_value(self, value: Primitives) -> list[str]:
        """
        Given a value, find all the paths that contain that value.

        NOTE: This only supports searching for "primitive" values, i.e. you cannot search for collections.

        :param value: Value to find in the recipe.
        :raises ValueError: If the value provided is not a primitive type.
        :returns: List of paths where the value can be found.
        """
        if not isinstance(value, PRIMITIVES_TUPLE):
            raise ValueError(f"A non-primitive value was provided: {value}")

        paths: list[str] = []

        def _find_value_paths(node: Node, path_stack: StrStack) -> None:
            # Special case: empty keys imply a null value, although they don't contain a null child.
            if (value is None and node.is_empty_key()) or (node.is_leaf() and node.value == value):
                paths.append(stack_path_to_str(path_stack))

        traverse_all(self._root, _find_value_paths)

        return paths

    ## General Convenience Functions ##

    def is_multi_output(self) -> bool:
        """
        Indicates if a recipe is a "multiple output" recipe.
        :returns: True if the recipe produces multiple outputs. False otherwise.
        """
        return self.contains_value("/outputs")

    def get_package_paths(self) -> list[str]:
        """
        Convenience function that returns the locations of all "outputs" in the `/outputs` directory AND the root/
        top-level of the recipe file. Combined with a call to `get_value()` with a default value and a for loop, this
        should easily allow the calling code to handle editing/examining configurations found in:
          - "Simple" (non-multi-output) recipe files
          - Multi-output recipe files
          - Recipes that have both top-level and multi-output sections. An example can be found here:
              https://github.com/AnacondaRecipes/curl-feedstock/blob/master/recipe/meta.yaml
        """
        paths: list[str] = ["/"]

        outputs: Final[list[str]] = cast(list[str], self.get_value("/outputs", []))
        for i in range(len(outputs)):
            paths.append(f"/outputs/{i}")

        return paths

    @staticmethod
    def append_to_path(base_path: str, ext_path: str) -> str:
        """
        Convenience function meant to be paired with `get_package_paths()` to generate extended paths. This handles
        issues that arise when concatenating paths that do or do not include a trailing/leading `/` character. Most
        notably, the root path `/` inherently contains a trailing `/`.
        :param base_path: Base path, provided by `get_package_paths()`
        :param ext_path: Path to append to the end of the `base_path`
        :returns: A normalized path constructed by the two provided paths.
        """
        # Ensure the base path always ends in a `/`
        if not base_path:
            base_path = "/"
        if base_path[-1] != "/":
            base_path += "/"
        # Ensure the extended path never starts with a `/`
        if ext_path and ext_path[0] == "/":
            ext_path = ext_path[1:]
        return f"{base_path}{ext_path}"

    def get_dependency_paths(self) -> list[str]:
        """
        Convenience function that returns a list of all dependency lines in a recipe.
        :returns: A list of all paths in a recipe file that point to dependencies.
        """
        paths: list[str] = []
        req_sections: Final[list[str]] = ["build", "host", "run", "run_constrained"]

        # Convenience function that reduces repeated logic between regular and multi-output recipes
        def _scan_requirements(path_prefix: str = "") -> None:
            for section in req_sections:
                section_path = f"{path_prefix}/requirements/{section}"
                # Relying on `get_value()` ensures that we will only examine literal values and ignore comments
                # in-between dependencies.
                dependencies = cast(list[str], self.get_value(section_path, []))
                for i in range(len(dependencies)):
                    paths.append(f"{section_path}/{i}")

        # Scan for both multi-output and non-multi-output recipes. Here is an example of a recipe that has both:
        #   https://github.com/AnacondaRecipes/curl-feedstock/blob/master/recipe/meta.yaml
        _scan_requirements()

        outputs = cast(list[JsonType], self.get_value("/outputs", []))
        for i in range(len(outputs)):
            _scan_requirements(f"/outputs/{i}")

        return paths

    ## Jinja Variable Functions ##

    def list_variables(self) -> list[str]:
        """
        Returns variables found in the recipe, sorted by first appearance.
        :returns: List of variables found in the recipe.
        """
        return list(self._vars_tbl.keys())

    def contains_variable(self, var: str) -> bool:
        """
        Determines if a variable is set in this recipe.
        :param var: Variable to check for.
        :returns: True if a variable name is found in this recipe. False otherwise.
        """
        return var in self._vars_tbl

    def get_variable(self, var: str, default: JsonType | SentinelType = _sentinel) -> JsonType:
        """
        Returns the value of a variable set in the recipe. If specified, a default value will be returned if the
        variable name is not found.
        :param var: Variable of interest check for.
        :param default: (Optional) If the value is not found, return this value instead.
        :raises KeyError: If the value is not found AND no default is specified
        :returns: The value (or specified default value if not found) of the variable name provided.
        """
        if var not in self._vars_tbl:
            if default == RecipeParser._sentinel or isinstance(default, SentinelType):
                raise KeyError
            return default
        return self._vars_tbl[var]

    def set_variable(self, var: str, value: JsonType) -> None:
        """
        Adds or changes an existing Jinja variable.
        :param var: Variable to modify
        :param value: Value to set
        """
        self._vars_tbl[var] = value
        self._is_modified = True

    def del_variable(self, var: str) -> None:
        """
        Remove a variable from the project. If one is not found, no changes are made.
        :param var: Variable to delete
        """
        if not var in self._vars_tbl:
            return
        del self._vars_tbl[var]
        self._is_modified = True

    def get_variable_references(self, var: str) -> list[str]:
        """
        Returns a list of paths that use particular variables.
        :param var: Variable of interest
        :returns: List of paths that use a variable, sorted by first appearance.
        """
        if var not in self._vars_tbl:
            return []

        path_list: list[str] = []
        # The text between the braces is very forgiving. Just searching for whitespace characters means we will never
        # match the very common `{{ name | lower }}` expression, or similar piping functions.
        var_re = re.compile(r"{{.*" + var + r".*}}")

        def _collect_var_refs(node: Node, path: StrStack) -> None:
            # Variables can only be found inside string values.
            if isinstance(node.value, str) and var_re.search(node.value):
                path_list.append(stack_path_to_str(path))

        traverse_all(self._root, _collect_var_refs)
        return dedupe_and_preserve_order(path_list)

    ## Selector Functions ##

    def list_selectors(self) -> list[str]:
        """
        Returns selectors found in the recipe, sorted by first appearance.
        :returns: List of selectors found in the recipe.
        """
        return list(self._selector_tbl.keys())

    def contains_selector(self, selector: str) -> bool:
        """
        Determines if a selector expression is present in this recipe.
        :param selector: Selector to check for.
        :returns: True if a selector is found in this recipe. False otherwise.
        """
        return selector in self._selector_tbl

    def get_selector_paths(self, selector: str) -> list[str]:
        """
        Given a selector (including the surrounding brackets), provide a list of paths in the parse tree that use that
        selector.

        Selector paths will be ordered by the line they appear on in the file.

        :param selector: Selector of interest.
        :returns: A list of all known paths that use a particular selector
        """
        # We return a tuple so that caller doesn't accidentally modify a private member variable.
        if not self.contains_selector(selector):
            return []
        path_list: list[str] = []
        for path_stack in self._selector_tbl[selector]:
            path_list.append(stack_path_to_str(path_stack.path))
        # The list should be de-duped and maintain order. Duplications occur when key-value pairings mean a selector
        # occurs on two nodes with the same path.
        #
        # For example:
        #   skip: True  # [unix]
        # The nodes for both `skip` and `True` contain the comment `[unix]`
        return dedupe_and_preserve_order(path_list)

    def contains_selector_at_path(self, path: str) -> bool:
        """
        Given a path, determine if a selector exists on that line.
        :param path: Target path
        :returns: True if the selector exists at that path. False otherwise.
        """
        path_stack = str_to_stack_path(path)
        node = traverse(self._root, path_stack)
        if node is None:
            return False
        return bool(Regex.SELECTOR.search(node.comment))

    def get_selector_at_path(self, path: str, default: str | SentinelType = _sentinel) -> str:
        """
        Given a path, return the selector that exists on that line.
        :param path: Target path
        :param default: (Optional) Default value to use if no selector is found.
        :raises KeyError: If a selector is not found on the provided path AND no default has been specified.
        :raises ValueError: If the default selector provided is malformed
        :returns: Selector on the path provided
        """
        path_stack = str_to_stack_path(path)
        node = traverse(self._root, path_stack)
        if node is None:
            raise KeyError(f"Path not found: {path}")

        search_results = Regex.SELECTOR.search(node.comment)
        if not search_results:
            # Use `default` case
            if default != RecipeParser._sentinel and not isinstance(default, SentinelType):
                if not Regex.SELECTOR.match(default):
                    raise ValueError(f"Invalid selector provided: {default}")
                return default
            raise KeyError(f"Selector not found at path: {path}")
        return search_results.group(0)

    def add_selector(self, path: str, selector: str, mode: SelectorConflictMode = SelectorConflictMode.REPLACE) -> None:
        """
        Given a path, add a selector (include the surrounding brackets) to the line denoted by path.
        :param path: Path to add a selector to
        :param selector: Selector statement to add
        :param mode: (Optional) Indicates how to handle a conflict if a selector already exists at this path.
        :raises KeyError: If the path provided is not found
        :raises ValueError: If the selector provided is malformed
        """
        path_stack = str_to_stack_path(path)
        node = traverse(self._root, path_stack)

        if node is None:
            raise KeyError(f"Path not found: {path!r}")
        if not Regex.SELECTOR.match(selector):
            raise ValueError(f"Invalid selector provided: {selector}")

        # Helper function that extracts the outer set of []'s in a selector
        def _extract_selector(s: str) -> str:
            return s.replace("[", "", 1)[::-1].replace("]", "", 1)[::-1]

        comment = ""
        old_selector_found = Regex.SELECTOR.search(node.comment)
        if node.comment == "" or mode == SelectorConflictMode.REPLACE:
            comment = f"# {selector}"
        # "Append" to existing selectors
        elif old_selector_found:
            logic_op = "and" if mode == SelectorConflictMode.AND else "or"
            old_selector = _extract_selector(old_selector_found.group())
            new_selector = _extract_selector(selector)
            comment = f"# [{old_selector} {logic_op} {new_selector}]"
        # If the comment is not a selector, put the selector first, then append the comment.
        else:
            # Strip the existing comment of it's leading `#` symbol
            comment = f"# {selector} {node.comment.replace('#', '', 1).strip()}"

        node.comment = comment
        # Some lines of YAML correspond to multiple nodes. For consistency, we need to ensure that comments are
        # duplicate across all nodes on a line.
        if node.is_single_key():
            node.children[0].comment = comment

        self._rebuild_selectors()
        self._is_modified = True

    def remove_selector(self, path: str) -> Optional[str]:
        """
        Given a path, remove a selector to the line denoted by path.
        - If a selector does not exist, nothing happens.
        - If a comment exists after the selector, keep it, discard the selector.
        :param path: Path to add a selector to
        :raises KeyError: If the path provided is not found
        :returns: If found, the selector removed (includes surrounding brackets). Otherwise, returns None
        """
        path_stack = str_to_stack_path(path)
        node = traverse(self._root, path_stack)

        if node is None:
            raise KeyError(f"Path not found: {path!r}")

        search_results = Regex.SELECTOR.search(node.comment)
        if not search_results:
            return None

        selector = search_results.group(0)
        comment = node.comment.replace(selector, "")
        # Sanitize potential edge-case scenarios after a removal
        comment = comment.replace("#  ", "# ").replace("# # ", "# ")
        # Detect and remove empty comments. Other comments should remain intact.
        if comment.strip() == "#":
            comment = ""

        node.comment = comment
        # Some lines of YAML correspond to multiple nodes. For consistency, we need to ensure that comments are
        # duplicate across all nodes on a line.
        if node.is_single_key():
            node.children[0].comment = comment

        self._rebuild_selectors()
        self._is_modified = True
        return selector

    ## Comment Functions ##

    def get_comments_table(self) -> dict[str, str]:
        """
        Returns a dictionary containing the location of every comment mapped to the value of the comment.
        NOTE:
            - Selectors are not considered to be comments.
            - Lines containing only comments are currently not addressable by our pathing scheme, so they are omitted.
              For our current purposes (of upgrading the recipe format) this should be fine. Non-addressable values
              should be less likely to be removed from patch operations.
        :returns: List of paths where comments can be found.
        """
        comments_tbl: dict[str, str] = {}

        def _track_comments(node: Node, path_stack: StrStack) -> None:
            if node.is_comment() or node.comment == "":
                return
            comment = node.comment
            # Handle comments found alongside a selector
            if Regex.SELECTOR.search(comment):
                comment = Regex.SELECTOR.sub("", comment).strip()
                # Sanitize common artifacts left from removing the selector
                comment = comment.replace("#  # ", "# ", 1).replace("#  ", "# ", 1)

                # Reject selector-only comments
                if comment in {"", "#"}:
                    return
                if comment[0] != "#":
                    comment = f"# {comment}"

            path = stack_path_to_str(path_stack)
            comments_tbl[path] = comment

        traverse_all(self._root, _track_comments)
        return comments_tbl

    def add_comment(self, path: str, comment: str) -> None:
        """
        Adds a comment to an existing path. If a comment exists, replaces the existing comment. If a selector exists,
        comment is appended after the selector component of the comment.
        :param path: Target path to add a comment to
        :param comment: Comment to add
        :raises KeyError: If the path provided is not found
        :raises ValueError: If the comment provided is a selector, the empty string, or consists of only whitespace
            characters
        """
        comment = comment.strip()
        if comment == "":
            raise ValueError("Comments cannot consist only of whitespace characters")

        if Regex.SELECTOR.match(comment):
            raise ValueError(f"Selectors can not be submitted as comments: {comment}")

        node = traverse(self._root, str_to_stack_path(path))

        if node is None:
            raise KeyError(f"Path not found: {path}")

        search_results = Regex.SELECTOR.search(node.comment)
        # If a selector is present, append the selector.
        if search_results:
            selector = search_results.group(0)
            if comment[0] == "#":
                comment = comment[1:].strip()
            comment = f"# {selector} {comment}"

        # Prepend a `#` if it is missing
        if comment[0] != "#":
            comment = f"# {comment}"
        node.comment = comment
        # Comments for "single key" nodes apply to both the parent and child. This is because such parent nodes render
        # on the same line as their children.
        if node.is_single_key():
            node.children[0].comment = comment
        self._is_modified = True

    ## YAML Patching Functions ##

    @staticmethod
    def _is_valid_patch_node(node: Optional[Node], node_idx: int) -> TypeGuard[Node]:
        """
        Indicates if the target node to perform a patch operation against is a valid node. This is based on the RFC spec
        for JSON patching paths.
        :param node: Target node to validate
        :param node_idx: If the caller is evaluating that a list member, exists, this is the VIRTUAL index into that
            list. Otherwise this value should be less than 0.
        :returns: True if the node can be patched. False otherwise.
        """
        # Path not found
        if node is None:
            return False

        # Leaf nodes contain values and not path information. Paths should not be made that access leaf nodes, with the
        # exception of members of a list and keys. Making such a path violates the RFC.
        if not node.list_member_flag and not node.key_flag and node.is_leaf():
            return False

        if node_idx >= 0:
            # Check the bounds if the target requires the use of an index, remembering to use the virtual look-up table.
            idx_map = remap_child_indices_virt_to_phys(node.children)
            if node_idx < 0 or node_idx > (len(idx_map) - 1):
                return False
            # You cannot use the list access feature to access non-lists
            if len(node.children) and not node.children[idx_map[node_idx]].list_member_flag:
                return False

        return True

    def _patch_add_find_target(self, path_stack: StrStack) -> tuple[Optional[Node], int, int, str, bool]:
        """
        Finds the target node of an `add()` operation, along with some supporting information.

        This function does not modify the parse tree.
        :param path_stack: Path that describes a location in the tree, as a list, treated like a stack.
        :returns: A tuple containing: - The target node, if found (or the parent node if the target is a list member) -
            The index of a node if the target is a list member - An additional path that needs to be created, if
            applicable - A flag indicating if the new data will be appended to a list
        """
        if len(path_stack) == 0:
            return None, INVALID_IDX, INVALID_IDX, "", False

        # Special case that only applies to `add`. The `-` character indicates the new element can be added to the end
        # of the list.
        append_to_list = False
        if path_stack[0] == "-":
            path_stack.pop(0)
            append_to_list = True

        path_stack_copy = path_stack.copy()
        node, virt_idx, phys_idx = traverse_with_index(self._root, path_stack)
        # Attempt to run a second time, if no node is found. As per the RFC, the containing object/list must exist. That
        # allows us to create only 1 level in the path.
        path_to_create = ""
        if node is None:
            path_to_create = path_stack_copy.pop(0)
            node, virt_idx, phys_idx = traverse_with_index(self._root, path_stack_copy)

        return node, virt_idx, phys_idx, path_to_create, append_to_list

    def _patch_add(self, path_stack: StrStack, value: JsonType) -> bool:
        """
        Performs a JSON patch `add` operation.
        :param path_stack: Path that describes a location in the tree, as a list, treated like a stack.
        :param value: Value to add.
        :returns: True if the operation was successful. False otherwise.
        """
        # NOTE from the RFC:
        #   Because this operation is designed to add to existing objects and arrays, its target location will often
        #   not exist...However, the object itself or an array containing it does need to exist
        # In other words, the patch op will, at most, create 1 new path level. In addition, that also implies that
        # trying to append to an existing list only applies if the append operator is at the end of the list.
        node, virt_idx, phys_idx, path_to_create, append_to_list = self._patch_add_find_target(path_stack)

        if not RecipeParser._is_valid_patch_node(node, virt_idx):
            return False

        # If we couldn't find 1 level in the path, ensure that we re-insert that as the "root" of the sub-tree we are
        # about to create.
        if path_to_create:
            value = {path_to_create: value}

        new_children: Final[list[Node]] = RecipeParser._generate_subtree(value)
        # Mark children as list members if they are list members
        if append_to_list or phys_idx >= 0:
            for child in new_children:
                child.list_member_flag = True

        # Insert members if an index is specified. Otherwise, extend the list of child nodes from the existing list.
        if phys_idx >= 0:
            node.children[phys_idx:phys_idx] = new_children
        # Extend the list of children if we're appending or adding a new key.
        elif append_to_list or path_to_create:
            node.children.extend(new_children)
        # NOTE from the RFC: "If the member already exists, it is replaced by the specified value."
        else:
            node.children = new_children

        return True

    def _patch_remove(self, path_stack: StrStack) -> bool:
        """
        Performs a JSON patch `remove` operation.
        :param path_stack: Path that describes a location in the tree, as a list, treated like a stack.
        :returns: True if the operation was successful. False otherwise.
        """
        if len(path_stack) == 0:
            return False

        # Removal in all scenarios requires targeting the parent node.
        node_idx = -1 if not path_stack[0].isdigit() else int(path_stack[0])
        # `traverse()` is destructive to the stack, so make a copy for the second traversal call.
        path_stack_copy = path_stack.copy()
        node_to_rm = traverse(self._root, path_stack)
        if not RecipeParser._is_valid_patch_node(node_to_rm, -1):
            return False

        path_stack_copy.pop(0)
        node = traverse(self._root, path_stack_copy)
        if not RecipeParser._is_valid_patch_node(node, node_idx):
            return False

        if node_idx >= 0:
            # Pop the "physical" index, not the "virtual" one to ensure comments have been accounted for.
            node.children.pop(remap_child_indices_virt_to_phys(node.children)[node_idx])
            return True

        # In all other cases, the node to be removed must be found before eviction
        for i in range(len(node.children)):
            if node.children[i] == node_to_rm:
                node.children.pop(i)
                return True
        return False

    def _patch_replace(self, path_stack: StrStack, value: JsonType) -> bool:
        """
        Performs a JSON patch `replace` operation.
        :param path_stack: Path that describes a location in the tree, as a list, treated like a stack.
        :param value: Value to update with.
        :returns: True if the operation was successful. False otherwise.
        """
        node, virt_idx, phys_idx = traverse_with_index(self._root, path_stack)
        if not RecipeParser._is_valid_patch_node(node, virt_idx):
            return False

        new_children: Final[list[Node]] = RecipeParser._generate_subtree(value)
        # Lists inject all children at the target position.
        if phys_idx >= 0:
            # Ensure all children are marked as list members
            for child in new_children:
                child.list_member_flag = True
            node.children[phys_idx:phys_idx] = new_children
            # Evict the old child, which is now behind the new children
            node.children.pop(phys_idx + len(new_children))
            return True

        # Leafs that represent values/paths of values can evict all children, and be replaced with new children, derived
        # from a new tree of values.
        node.children = new_children
        return True

    def _patch_move(self, path_stack: StrStack, value_from: str) -> bool:
        """
        Performs a JSON patch `add` operation.
        :param path_stack: Path that describes a location in the tree, as a list, treated like a stack.
        :param value_from: The "from" value in the JSON payload, i.e. the path the value originates from.
        :returns: True if the operation was successful. False otherwise.
        """
        # NOTE from the RFC:
        #   This operation is functionally identical to a "remove" operation on the "from" location, followed
        #   immediately by an "add" operation at the target location with the value that was just removed.
        # So to save on development and maintenance, that is how this op is written.
        original_value: JsonType
        try:
            original_value = self.get_value(value_from)
        except KeyError:
            return False

        # Validate that `add`` will succeed before we `remove` anything
        node, virt_idx, _, _, _ = self._patch_add_find_target(path_stack.copy())
        if not RecipeParser._is_valid_patch_node(node, virt_idx):
            return False

        return self._patch_remove(str_to_stack_path(value_from)) and self._patch_add(path_stack, original_value)

    def _patch_copy(self, path_stack: StrStack, value_from: str) -> bool:
        """
        Performs a JSON patch `add` operation.
        :param path_stack: Path that describes a location in the tree, as a list, treated like a stack.
        :param value_from: The "from" value in the JSON payload, i.e. the path the value originates from.
        :returns: True if the operation was successful. False otherwise.
        """
        # NOTE from the RFC:
        #   This operation is functionally identical to an "add" operation at the target location using the value
        #   specified in the "from" member.
        # So to save on development and maintenance, that is how this op is written.
        original_value: JsonType
        try:
            original_value = self.get_value(value_from)
        except KeyError:
            return False

        return self._patch_add(path_stack, original_value)

    def _patch_test(self, path: str, value: JsonType) -> bool:
        """
        Performs a JSON patch `test` operation.
        :param path: Path as a string. Useful for invoking public class members.
        :param value: Value to evaluate against.
        :returns: True if the target value is equal to the provided value. False otherwise.
        """
        try:
            return self.get_value(path) == value
        except KeyError:
            # Path not found
            return False

    def _call_patch_op(self, op: str, path: str, patch: JsonPatchType) -> bool:
        """
        Switching function that calls the appropriate JSON patch operation.
        :param op: Patch operation, pre-sanitized.
        :param path: Path as a string.
        :param patch: The original JSON patch. This is passed to conditionally provide extra arguments, per op.
        :returns: True if the patch was successful. False otherwise.
        """
        path_stack: Final[StrStack] = str_to_stack_path(path)
        # NOTE: The `remove` op has no `value` or `from` field to pass in, so it is executed first.
        if op == "remove":
            return self._patch_remove(path_stack)

        # The supplemental field name is determined by the operation type.
        value_from: Final[str] = "from" if op in RecipeParser._patch_ops_requiring_from else "value"
        patch_data: Final[JsonType | str] = patch[value_from]

        if op == "add":
            return self._patch_add(path_stack, patch_data)
        if op == "replace":
            return self._patch_replace(path_stack, patch_data)
        if op == "move":
            return self._patch_move(path_stack, cast(str, patch_data))
        if op == "copy":
            return self._patch_copy(path_stack, cast(str, patch_data))
        if op == "test":
            return self._patch_test(path, patch_data)

        # This should be unreachable but is kept for completeness.
        return False

    def patch(self, patch: JsonPatchType) -> bool:
        """
        Given a JSON-patch object, perform a patch operation.

        Modifications from RFC 6902
          - We're using a Jinja-formatted YAML file, not JSON
          - To modify comments, specify the `path` AND `comment`

        :param patch: JSON-patch payload to operate with.
        :raises JsonPatchValidationException: If the JSON-patch payload does not conform to our schema/spec.
        :returns: If the calling code attempts to perform the `test` operation, this indicates the return value of the
            `test` request. In other words, if `value` matches the target variable, return True. False otherwise. For
            all other operations, this indicates if the operation was successful.
        """
        # Validate the patch schema
        try:
            schema_validate(patch, JSON_PATCH_SCHEMA)
        except Exception as e:
            raise JsonPatchValidationException(patch) from e

        path: Final[str] = cast(str, patch["path"])

        # All RFC ops are supported, so the JSON schema validation checks will prevent us from getting this far, if
        # there is an issue.
        op: Final[str] = cast(str, patch["op"])

        # A no-op move is silly, but we might as well make it efficient AND ensure a no-op move doesn't corrupt our
        # modification flag.
        if op == "move" and path == patch["from"]:
            return True

        # Both versions of the path are sent over so that the op can easily use both private and public functions
        # (without incurring even more conversions between path types).
        is_successful = self._call_patch_op(op, path, patch)

        # Update the selector table and modified flag, if the operation succeeded.
        if is_successful and op != "test":
            # TODO this is not the most efficient way to update the selector table, but for now, it works.
            self._rebuild_selectors()
            # TODO technically this doesn't handle a no-op.
            self._is_modified = True

        return is_successful

    def search(self, regex: str | re.Pattern[str], include_comment: bool = False) -> list[str]:
        """
        Given a regex string, return the list of paths that match the regex.
        NOTE: This function only searches against primitive values. All variables and selectors can be fully provided by
              using their respective `list_*()` functions.

        :param regex: Regular expression to match with
        :param include_comment: (Optional) If set to `True`, this function will execute the regular expression on values
            WITH their comments provided. For example: `42  # This is a comment`
        :returns: Returns a list of paths where the matched value was found.
        """
        re_obj = re.compile(regex)
        paths: list[str] = []

        def _search_paths(node: Node, path_stack: StrStack) -> None:
            value = str(stringify_yaml(node.value))
            if include_comment and node.comment:
                value = f"{value}{TAB_AS_SPACES}{node.comment}"
            if node.is_leaf() and re_obj.search(value):
                paths.append(stack_path_to_str(path_stack))

        traverse_all(self._root, _search_paths)

        return paths

    def search_and_patch(
        self, regex: str | re.Pattern[str], patch: JsonPatchType, include_comment: bool = False
    ) -> bool:
        """
        Given a regex string and a JSON patch, apply the patch to any values that match the search expression.
        :param regex: Regular expression to match with
        :param patch: JSON patch to perform. NOTE: The `path` field will be replaced with the path(s) found, so it does
            not need to be provided.
        :param include_comment: (Optional) If set to `True`, this function will execute the regular expression on values
            WITH their comments provided. For example: `42  # This is a comment`
        :returns: Returns a list of paths where the matched value was found.
        """
        paths = self.search(regex, include_comment)
        summation: bool = True
        for path in paths:
            patch["path"] = path
            summation = summation and self.patch(patch)
        return summation

    def diff(self) -> str:
        """
        Returns a git-like-styled diff of the current recipe state with original state of the recipe. Useful for
        debugging and providing users with some feedback.
        :returns: User-friendly displayable string that represents notifications made to the recipe.
        """
        if not self.is_modified():
            return ""
        # Utilize `difflib` to lower maintenance overhead.
        return "\n".join(
            difflib.unified_diff(
                self._init_content.splitlines(), self.render().splitlines(), fromfile="original", tofile="current"
            )
        )
