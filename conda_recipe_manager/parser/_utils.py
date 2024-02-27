"""
File:           _utils.py
Description:    Provides private utility functions only used by the parser.
"""
from __future__ import annotations

import json
from typing import cast

from percy.parser._types import PERCY_SUB_MARKER, ROOT_NODE_VALUE, Regex, StrStack, StrStackImmutable
from percy.parser.types import TAB_AS_SPACES, MultilineVariant, NodeValue
from percy.types import H, SentinelType


def str_to_stack_path(path: str) -> StrStack:
    """
    Takes a JSON-patch path as a string and return a path as a stack of strings. String paths are used by callers,
    stacks are used internally.

    For example:
        "/foo/bar/baz" -> ["baz", "bar", "foo", "/"]
    :param path: Path to deconstruct into a stack
    :returns: Path, described as a stack of strings.
    """
    # TODO: validate the path starts with `/` (root)

    # `PurePath` could be used here, but isn't for performance gains.
    # TODO reduce 3 (O)n operations to 1 O(n) operation

    # Wipe the trailing `/`, if provided. It doesn't have meaning here; only the `root` path is tracked.
    if path[-1] == ROOT_NODE_VALUE:
        path = path[:-1]
    parts = path.split("/")
    # Replace empty strings with `/` for compatibility in other functions.
    for i in range(0, len(parts)):
        if parts[i] == "":
            parts[i] = "/"
    return parts[::-1]


def stack_path_to_str(path_stack: StrStack | StrStackImmutable) -> str:
    """
    Takes a stack that represents a path and converts it into a string. String paths are used by callers, stacks are
    used internally.

    :param path_stack: Stack to construct back into a string.
    :returns: Path, described as a string.
    """
    # Normalize type if a tuple is given.
    if isinstance(path_stack, tuple):
        path_stack = list(path_stack)
    path = ""
    while len(path_stack) > 0:
        value = path_stack.pop()
        # Special case to bootstrap root; the first element will automatically add the first slash.
        if value == ROOT_NODE_VALUE:
            continue
        path += f"/{value}"
    return path


def num_tab_spaces(s: str) -> int:
    """
    Counts the number of spaces at the start of the string. Used to indicate depth of a field in a YAML file (the YAML
    specification dictates only spaces can be used for indenting).
    :param s: Target string
    :returns: Number of preceding spaces in a string
    """
    cntr: int = 0
    for c in s:
        if c == " ":
            cntr += 1
        else:
            break
    return cntr


def substitute_markers(s: str, subs: list[str]) -> str:
    """
    Given a string, replace substitution markers with the original Jinja template from a list of options.
    :param s: String to replace substitution markers with
    :param subs: List of substitutions to make, in order of appearance
    :returns: New string, with substitutions removed
    """
    while s.find(PERCY_SUB_MARKER) >= 0 and len(subs):
        s = s.replace(PERCY_SUB_MARKER, subs[0], 1)
        subs.pop(0)
    return s


def stringify_yaml(
    val: NodeValue | SentinelType, multiline_variant: MultilineVariant = MultilineVariant.NONE
) -> NodeValue:
    """
    Special function for handling edge cases when converting values back to YAML.
    :param val: Value to check
    :param multiline_variant: (Optional) If the value being processed is a multiline string, indicate which YAML
        descriptor is in use.
    :returns: YAML version of a value, as a string.
    """
    # Handled for type-completeness of `Node.value`. A `Node` with a sentinel as its value indicates a special Node
    # type that is not directly render-able.
    if isinstance(val, SentinelType):
        return ""
    # None -> null
    if val is None:
        return "null"
    # True -> true
    if isinstance(val, bool):
        if val:
            return "true"
        return "false"
    # Ensure string quote escaping if quote marks are present. Otherwise this has the unintended consequence of
    # quoting all YAML strings. Although not wrong, it does not follow our common practices. Quote escaping is not
    # required for multiline strings. We do not escape quotes for Jinja value statements. We make an exception for
    # strings containing the NEW recipe format syntax, ${{ }}, which is valid YAML.
    if multiline_variant == MultilineVariant.NONE and isinstance(val, str) and not Regex.JINJA_SUB.match(val):
        if "${{" not in val and ("'" in val or '"' in val):
            # The PyYaml equivalent function injects newlines, hence why we abuse the JSON library to write our YAML
            return json.dumps(val)
    return val


def normalize_multiline_strings(val: NodeValue, variant: MultilineVariant) -> NodeValue:
    """
    Utility function that takes in a Node's value and "normalizes" multiline strings so that they can be accurately
    interpreted by PyYaml. We use PyYaml to handle the various ways in which a multiline string can be interpreted.
    :param val: Value to normalize
    :param variant: Multiline variant rules to follow
    :returns: If the value is a multiline string, this returns the "normalized" string to be re-evaluated by PyYaml.
        Otherwise, returns the original value.
    """
    if variant == MultilineVariant.NONE:
        return val

    # Prepend the multiline marker to the string to have PyYaml interpret how the whitespace should be handled. JINJA
    # substitutions in multi-line strings do not break the PyYaml parser.
    multiline_str = f"\n{TAB_AS_SPACES}".join(cast(list[str], val))
    return f"{variant}\n{TAB_AS_SPACES}{multiline_str}"


def dedupe_and_preserve_order(l: list[H]) -> list[H]:
    """
    Takes a list of strings
    See this StackOverflow post:
      https://stackoverflow.com/questions/480214/how-do-i-remove-duplicates-from-a-list-while-preserving-order

    """
    return list(cast(dict[H, None], dict.fromkeys(l)))
