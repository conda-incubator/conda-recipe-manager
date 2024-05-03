"""
File:           recipe_parser_convert.py
Description:    Provides a subclass of RecipeParser that performs the conversion of a v0 recipe to the new v1 recipe
                format. This tooling was originally part of the base class, but was broken-out for easier/cleaner code
                maintenance.
"""

from __future__ import annotations

from typing import Final, Optional, cast

from conda_recipe_manager.parser._node import Node
from conda_recipe_manager.parser._traverse import traverse
from conda_recipe_manager.parser._types import (
    ROOT_NODE_VALUE,
    TOP_LEVEL_KEY_SORT_ORDER,
    V1_BUILD_SECTION_KEY_SORT_ORDER,
    V1_SOURCE_SECTION_KEY_SORT_ORDER,
    Regex,
)
from conda_recipe_manager.parser._utils import stack_path_to_str, str_to_stack_path
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.types import CURRENT_RECIPE_SCHEMA_FORMAT, MessageCategory, MessageTable
from conda_recipe_manager.types import JsonPatchType, JsonType, SentinelType


class RecipeParserConvert(RecipeParser):
    """
    Extension of the base RecipeParser class to enables upgrading recipes from the old to V1 format.
    This was originally part of the RecipeParser class but was broken-out for easier maintenance.
    """

    def __init__(self, content: str):
        """
        Constructs a convertible recipe object. This extension of the parser class keeps a modified copy of the original
        recipe to work on and tracks some debugging state.
        :param content: conda-build formatted recipe file, as a single text string.
        """
        super().__init__(content)
        # `copy.deepcopy()` produced some bizarre artifacts, namely single-line comments were being incorrectly rendered
        # as list members. Although inefficient, we have tests that validate round-tripping the parser and there
        # is no development cost in utilizing tools we already must maintain.
        self._v1_recipe: RecipeParser = RecipeParser(self.render())
        self._msg_tbl = MessageTable()

    ## Patch utility functions ##

    def _patch_and_log(self, patch: JsonPatchType) -> None:
        """
        Convenience function that logs failed patches to the message table.
        :param patch: Patch operation to perform
        """
        if not self._v1_recipe.patch(patch):
            self._msg_tbl.add_message(MessageCategory.ERROR, f"Failed to patch: {patch}")

    def _patch_add_missing_path(self, base_path: str, ext: str, value: JsonType = None) -> None:
        """
        Convenience function that constructs missing paths. Useful when you have to construct more than 1 path level at
        once (the JSON patch standard only allows the creation of 1 new level at a time).
        :param base_path: Base path, to be extended
        :param ext: Extension to create the full path to check for
        :param value: `value` field for the patch-add operation
        """
        temp_path: Final[str] = RecipeParser.append_to_path(base_path, ext)
        if self._v1_recipe.contains_value(temp_path):
            return
        self._patch_and_log({"op": "add", "path": temp_path, "value": value})

    def _patch_move_base_path(self, base_path: str, old_ext: str, new_ext: str) -> None:
        """
        Convenience function that moves a value under an old path to a new one sharing a common base path BUT only if
        the old path exists.
        :param base_path: Shared base path from old and new locations
        :param old_ext: Old extension to the base path containing the data to move
        :param new_ext: New extension to the base path of where the data should go
        """
        old_path: Final[str] = RecipeParser.append_to_path(base_path, old_ext)
        if not self._v1_recipe.contains_value(old_path):
            return
        self._patch_and_log({"op": "move", "from": old_path, "path": RecipeParser.append_to_path(base_path, new_ext)})

    def _patch_move_new_path(self, base_path: str, old_ext: str, new_path: str, new_ext: Optional[str] = None) -> None:
        """
        Convenience function that moves an old path to a new path that is now under a new path that must be
        conditionally added, if it is not present.

        Examples:
            `/build/entry_points` -> `/build/python/entry_points`
            `/build/missing_dso_whitelist` -> `build/dynamic_linking/missing_dso_allowlist`
        :param base_path: Shared base path from old and new locations
        :param old_ext: Old extension to the base path containing the data to move
        :param new_path: New path to extend to the base path, if the path does not currently exist
        :param new_ext: (Optional) New extension to the base path of where the data should go. Use this when the
            target value has been renamed. Defaults to the value of `old_ext`.
        """
        if new_ext is None:
            new_ext = old_ext
        if self._v1_recipe.contains_value(RecipeParser.append_to_path(base_path, old_ext)):
            self._patch_add_missing_path(base_path, new_path)
        self._patch_move_base_path(base_path, old_ext, RecipeParser.append_to_path(new_path, new_ext))

    def _sort_subtree_keys(self, sort_path: str, tbl: dict[str, int], rename: str = "") -> None:
        """
        Convenience function that sorts 1 level of keys, given a path. Optionally allows renaming of the target node.
        :param sort_path: Top-level path to target sorting of child keys
        :param tbl: Table describing how keys should be sorted. Lower-value key names appear towards the top of the list
        :param rename: (Optional) If specified, renames the top-level key
        """

        def _comparison(n: Node) -> int:
            return RecipeParser._canonical_sort_keys_comparison(n, tbl)

        node = traverse(self._v1_recipe._root, str_to_stack_path(sort_path))  # pylint: disable=protected-access
        if node is None:
            self._msg_tbl.add_message(MessageCategory.WARNING, f"Failed to sort members of {sort_path}")
            return
        if rename:
            node.value = rename
        node.children.sort(key=_comparison)

    ## Upgrade functions ##

    def _upgrade_jinja_to_context_obj(self) -> None:
        """
        Upgrades the old proprietary JINJA templating usage to the new YAML-parsable `context` object and `$`-escaped
        JINJA substitutions.
        """
        # Convert the JINJA variable table to a `context` section. Empty tables still add the `context` section for
        # future developers' convenience.
        self._patch_and_log({"op": "add", "path": "/context", "value": None})
        # Filter-out any value not covered in the V1 format
        for name, value in self._v1_recipe._vars_tbl.items():  # pylint: disable=protected-access
            if not isinstance(value, (str, int, float, bool)):
                self._msg_tbl.add_message(MessageCategory.WARNING, f"The variable `{name}` is an unsupported type.")
                continue
            self._patch_and_log({"op": "add", "path": f"/context/{name}", "value": value})

        # Similarly, patch-in the new `schema_version` value to the top of the file
        self._patch_and_log({"op": "add", "path": "/schema_version", "value": CURRENT_RECIPE_SCHEMA_FORMAT})

        # Swap all JINJA to use the new `${{ }}` format.
        jinja_sub_locations: Final[list[str]] = self._v1_recipe.search(Regex.JINJA_SUB)
        for path in jinja_sub_locations:
            value = self._v1_recipe.get_value(path)
            # Values that match the regex should only be strings. This prevents crashes that should not occur.
            if not isinstance(value, str):
                self._msg_tbl.add_message(
                    MessageCategory.WARNING, f"A non-string value was found as a JINJA substitution: {value}"
                )
                continue
            value = value.replace("{{", "${{")
            self._patch_and_log({"op": "replace", "path": path, "value": value})

    def _upgrade_selectors_to_conditionals(self) -> None:
        """
        Upgrades the proprietary comment-based selector syntax to equivalent conditional logic statements.
        """
        for selector, instances in self._v1_recipe._selector_tbl.items():  # pylint: disable=protected-access
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
                patch: JsonPatchType = {
                    "op": "replace",
                    "path": selector_path,
                    "value": "${{ true if " + bool_expression + " }}",
                }
                # `skip` is special and needs to be a list of boolean expressions.
                if selector_path.endswith("/build/skip"):
                    patch["value"] = [bool_expression]
                if not isinstance(info.node.value, bool):
                    # CEP-13 states that ONLY list members may use the `if/then/else` blocks
                    if not info.node.list_member_flag:
                        self._msg_tbl.add_message(
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
                        "value": cast(JsonType, bool_object),
                    }
                # Apply the patch
                self._patch_and_log(patch)
                self._v1_recipe.remove_selector(selector_path)

    def _upgrade_source_section(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts the `source` section(s) of a recipe file.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        for base_path in base_package_paths:
            source_path = RecipeParser.append_to_path(base_path, "/source")
            if not self._v1_recipe.contains_value(source_path):
                continue

            # The `source` field can contain a list of elements or a single element (not encapsulated in a list).
            # This logic sets up a list to iterate through that will handle both cases.
            source_data = self._v1_recipe.get_value(source_path)
            source_paths = []
            if isinstance(source_data, list):
                for x in range(len(source_data)):
                    source_paths.append(RecipeParser.append_to_path(source_path, f"/{x}"))
            else:
                source_paths.append(source_path)

            for src_path in source_paths:
                # SVN and HG source options are no longer supported. This seems to have been deprecated a long
                # time ago and there are unlikely any recipes that fall into this camp. Still, we should flag it.
                if self._v1_recipe.contains_value(RecipeParser.append_to_path(src_path, "svn_url")):
                    self._msg_tbl.add_message(
                        MessageCategory.WARNING, "SVN packages are no longer supported in the V1 format"
                    )
                if self._v1_recipe.contains_value(RecipeParser.append_to_path(src_path, "hg_url")):
                    self._msg_tbl.add_message(
                        MessageCategory.WARNING, "HG (Mercurial) packages are no longer supported in the V1 format"
                    )

                # Basic renaming transformations
                self._patch_move_base_path(src_path, "/fn", "/file_name")
                self._patch_move_base_path(src_path, "/folder", "/target_directory")

                # Canonically sort this section
                self._sort_subtree_keys(src_path, V1_SOURCE_SECTION_KEY_SORT_ORDER)

    def _upgrade_build_section(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts the `about` section(s) of a recipe file.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        for base_path in base_package_paths:
            # Move `run_exports` and `ignore_run_exports` from `build` to `requirements`

            # `run_exports`
            old_re_path = RecipeParser.append_to_path(base_path, "/build/run_exports")
            if self._v1_recipe.contains_value(old_re_path):
                requirements_path = RecipeParser.append_to_path(base_path, "/requirements")
                new_re_path = RecipeParser.append_to_path(base_path, "/requirements/run_exports")
                if not self._v1_recipe.contains_value(requirements_path):
                    self._patch_and_log({"op": "add", "path": requirements_path, "value": None})
                self._patch_and_log({"op": "move", "from": old_re_path, "path": new_re_path})
            # `ignore_run_exports`
            old_ire_path = RecipeParser.append_to_path(base_path, "/build/ignore_run_exports")
            if self._v1_recipe.contains_value(old_re_path):
                requirements_path = RecipeParser.append_to_path(base_path, "/requirements")
                new_ire_path = RecipeParser.append_to_path(base_path, "/requirements/ignore_run_exports")
                if not self._v1_recipe.contains_value(requirements_path):
                    self._patch_and_log({"op": "add", "path": requirements_path, "value": None})
                self._patch_and_log({"op": "move", "from": old_ire_path, "path": new_ire_path})

            # Perform internal section changes per `build/` section
            build_path = RecipeParser.append_to_path(base_path, "/build")
            if not self._v1_recipe.contains_value(build_path):
                continue

            # Simple transformations
            self._patch_move_base_path(build_path, "merge_build_host", "merge_build_and_host_envs")
            self._patch_move_base_path(build_path, "no_link", "always_copy_files")

            # `build/entry_points` -> `build/python/entry_points`
            self._patch_move_new_path(build_path, "/entry_points", "/python")

            # New `dynamic_linking` section changes
            self._patch_move_new_path(
                build_path, "/missing_dso_whitelist", "/dynamic_linking", "/missing_dso_allowlist"
            )
            self._patch_move_new_path(build_path, "/runpath_whitelist", "/dynamic_linking", "/rpath_allowlist")

            # Canonically sort this section
            self._sort_subtree_keys(build_path, V1_BUILD_SECTION_KEY_SORT_ORDER)

    def _upgrade_about_section(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts the `about` section of a recipe file.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        about_rename_mapping: Final[list[tuple[str, str]]] = [
            ("home", "homepage"),
            ("dev_url", "repository"),
            ("doc_url", "documentation"),
        ]
        about_deprecated: Final[list[str]] = [
            "prelink_message",
            "license_family",
            "identifiers",
            "tags",
            "keywords",
            "doc_source_url",
        ]

        for base_path in base_package_paths:
            about_path = RecipeParser.append_to_path(base_path, "/about")

            # Skip transformations if there is no `/about` section
            if not self._v1_recipe.contains_value(about_path):
                continue

            # Transform renamed fields
            for old, new in about_rename_mapping:
                self._patch_move_base_path(about_path, old, new)

            # TODO validate: /about/license must be SPDX recognized.

            # Remove deprecated `about` fields
            for field in about_deprecated:
                path = RecipeParser.append_to_path(about_path, field)
                if self._v1_recipe.contains_value(path):
                    self._patch_and_log({"op": "remove", "path": path})

    def _upgrade_test_pip_check(self, base_path: str, test_path: str) -> None:
        """
        Replaces the commonly used `pip check` test-case with the new `python/pip_check` attribute, if applicable.
        :param base_path: Base path for the build target to upgrade
        :param test_path: Test path for the build target to upgrade
        """
        # Replace `- pip check` in `commands` with the new flag. If not found, set the flag to `False` (as the
        # flag defaults to `True`). DO NOT ADD THIS FLAG IF THE RECIPE IS NOT A "PYTHON RECIPE".
        if "python" not in cast(
            list[str],
            self._v1_recipe.get_value(RecipeParser.append_to_path(base_path, "/requirements/host"), default=[]),
        ):
            return

        commands = cast(list[str], self._v1_recipe.get_value(RecipeParser.append_to_path(test_path, "/commands"), []))
        pip_check = False
        for i, command in enumerate(commands):
            if command != "pip check":
                continue
            # For now, we will only patch-out the first instance when no selector is attached
            # TODO Future: handle selector logic/cases with `pip check || <bool>`
            self._patch_and_log({"op": "remove", "path": RecipeParser.append_to_path(test_path, f"/commands/{i}")})
            pip_check = True
            break
        self._patch_add_missing_path(test_path, "/python")
        self._patch_and_log(
            {"op": "add", "path": RecipeParser.append_to_path(test_path, "/python/pip_check"), "value": pip_check}
        )

    def _upgrade_test_section(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts the `test` section(s) of a recipe file.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        # NOTE: For now, we assume that the existing test section comprises of a single test entity. Developers will
        # have to use their best judgement to manually break-up the test into multiple tests as they see fit.
        for base_path in base_package_paths:
            test_path = RecipeParser.append_to_path(base_path, "/test")
            if not self._v1_recipe.contains_value(test_path):
                continue

            # Moving `files` to `files/recipe` is not possible in a single `move` operation as a new path has to be
            # created in the path being moved.
            test_files_path = RecipeParser.append_to_path(test_path, "/files")
            if self._v1_recipe.contains_value(test_files_path):
                test_files_value = self._v1_recipe.get_value(test_files_path)
                # TODO: Fix, replace does not work here, produces `- null`, Issue #20
                # self._patch_and_log({"op": "replace", "path": test_files_path, "value": None})
                self._patch_and_log({"op": "remove", "path": test_files_path})
                self._patch_and_log({"op": "add", "path": test_files_path, "value": None})
                self._patch_and_log(
                    {
                        "op": "add",
                        "path": RecipeParser.append_to_path(test_files_path, "/recipe"),
                        "value": test_files_value,
                    }
                )
            # Edge case: `/source_files` exists but `/files` does not
            elif self._v1_recipe.contains_value(RecipeParser.append_to_path(test_path, "/source_files")):
                self._patch_add_missing_path(test_path, "/files")
            self._patch_move_base_path(test_path, "/source_files", "/files/source")

            if self._v1_recipe.contains_value(RecipeParser.append_to_path(test_path, "/requires")):
                self._patch_add_missing_path(test_path, "/requirements")
            self._patch_move_base_path(test_path, "/requires", "/requirements/run")

            # Upgrade `pip-check`, if applicable
            self._upgrade_test_pip_check(base_path, test_path)

            self._patch_move_base_path(test_path, "/commands", "/script")
            if self._v1_recipe.contains_value(RecipeParser.append_to_path(test_path, "/imports")):
                self._patch_add_missing_path(test_path, "/python")
                self._patch_move_base_path(test_path, "/imports", "/python/imports")
            self._patch_move_base_path(test_path, "/downstreams", "/downstream")

            # Move `test` to `tests` and encapsulate the pre-existing object into a list
            new_test_path = f"{test_path}s"
            test_element = cast(dict[str, JsonType], self._v1_recipe.get_value(test_path))
            test_array: list[JsonType] = []
            # There are 3 types of test elements. We break them out of the original object, if they exist.
            # `Python` Test Element
            if "python" in test_element:
                test_array.append({"python": test_element["python"]})
                del test_element["python"]
            # `Downstream` Test Element
            if "downstream" in test_element:
                test_array.append({"downstream": test_element["downstream"]})
                del test_element["downstream"]
            # What remains should be the `Command` Test Element type
            if test_element:
                test_array.append(test_element)
            self._patch_and_log({"op": "add", "path": new_test_path, "value": test_array})
            self._patch_and_log({"op": "remove", "path": test_path})

    def _upgrade_multi_output(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts sections pertaining to multi-output recipes.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        if not self._v1_recipe.contains_value("/outputs"):
            return

        # TODO Complete
        # On the top-level, `package` -> `recipe`
        self._patch_move_base_path(ROOT_NODE_VALUE, "/package", "/recipe")

        for output_path in base_package_paths:
            if output_path == ROOT_NODE_VALUE:
                continue

            # Move `name` and `version` under `package`
            if self._v1_recipe.contains_value(
                RecipeParser.append_to_path(output_path, "/name")
            ) or self._v1_recipe.contains_value(RecipeParser.append_to_path(output_path, "/version")):
                self._patch_add_missing_path(output_path, "/package")
            self._patch_move_base_path(output_path, "/name", "/package/name")
            self._patch_move_base_path(output_path, "/version", "/package/version")

            # Not all the top-level keys are found in each output section, but all the output section keys are
            # found at the top-level. So for consistency, we sort on that ordering.
            self._sort_subtree_keys(output_path, TOP_LEVEL_KEY_SORT_ORDER)

    @staticmethod
    def pre_process_recipe_text(content: str) -> str:
        """
        Takes the content of a recipe file and performs manipulations prior to the parsing stage. This should be
        used sparingly for solving conversion issues.

        Ideally the pre-processor phase is only used when:
          - There is no other feasible way to solve a conversion issue.
          - There is a proof-of-concept fix that would be easier to develop as a pre-processor step that could be
            refactored into the parser later.
          - The number of recipes afflicted by an issue does not justify the engineering effort required to handle
            the issue in the parsing phase.
        :param content: Recipe file contents to pre-process
        :returns: Pre-processed recipe file contents
        """
        # Convert the old JINJA `environ[""]` variable usage to the new `get.env("")` syntax.
        # NOTE:
        #   - This is mostly used by Bioconda recipes and R-based-packages in the `license_file` field.
        #   - From our search, it looks like we never deal with more than one set of outer quotes within the brackets
        replacements: list[tuple[str, str]] = []
        for groups in cast(list[str], Regex.PRE_PROCESS_ENVIRON.findall(content)):
            # Each match should return ["<quote char>", "<key>", "<quote_char>"]
            quote_char = groups[0]
            key = groups[1]
            replacements.append(
                (
                    f"environ[{quote_char}{key}{quote_char}]",
                    f"env.get({quote_char}{key}{quote_char})",
                )
            )
        for old, new in replacements:
            content = content.replace(old, new, 1)

        return content

    def render_to_v1_recipe_format(self) -> tuple[str, MessageTable, RecipeParser]:
        """
        Takes the current recipe representation and renders it to the V1 format WITHOUT modifying the current recipe
        state.

        This "new" format is defined in the following CEPs:
          - https://github.com/conda-incubator/ceps/blob/main/cep-13.md
          - https://github.com/conda-incubator/ceps/blob/main/cep-14.md

        :returns: Returns a tuple containing:
            - The converted recipe, as a string
            - A `MessageTbl` instance that contains error logging
            - The `RecipeParser` instance containing the converted recipe file. USE FOR DEBUGGING PURPOSES ONLY!
        """
        # Approach: In the event that we want to expand support later, this function should be implemented in terms
        # of a `RecipeParser` tree. This will make it easier to build an upgrade-path, if we so choose to pursue one.

        # Log the original comments
        old_comments: Final[dict[str, str]] = self._v1_recipe.get_comments_table()

        # Convert selectors into ternary statements or `if` blocks. We process selectors first so that there is no
        # chance of selector comments getting accidentally wiped by patch or other operations.
        self._upgrade_selectors_to_conditionals()

        # JINJA templates -> `context` object
        self._upgrade_jinja_to_context_obj()

        # Cached copy of all of the "outputs" in a recipe. This is useful for easily handling multi and single output
        # recipes in 1 loop construct.
        base_package_paths: Final[list[str]] = self._v1_recipe.get_package_paths()

        # TODO Fix: comments are not preserved with patch operations (add a flag to `patch()`?)

        # Upgrade common sections found in a recipe
        self._upgrade_source_section(base_package_paths)
        self._upgrade_build_section(base_package_paths)
        self._upgrade_about_section(base_package_paths)
        self._upgrade_test_section(base_package_paths)
        self._upgrade_multi_output(base_package_paths)

        ## Final clean-up ##

        # TODO: Comment tracking may need improvement. The "correct way" of tracking comments with patch changes is a
        #       fairly big engineering effort and refactor.
        # Alert the user which comments have been dropped.
        new_comments: Final[dict[str, str]] = self._v1_recipe.get_comments_table()
        diff_comments: Final[dict[str, str]] = {k: v for k, v in old_comments.items() if k not in new_comments}
        for path, comment in diff_comments.items():
            if not self._v1_recipe.contains_value(path):
                self._msg_tbl.add_message(MessageCategory.WARNING, f"Could not relocate comment: {comment}")

        # TODO Complete: move operations may result in empty fields we can eliminate. This may require changes to
        #                `contains_value()`
        # TODO Complete: Attempt to combine consecutive If/Then blocks after other modifications. This should reduce the
        #                risk of screwing up critical list indices and ordering.

        # Hack: Wipe the existing table so the JINJA `set` statements don't render the final form
        self._v1_recipe._vars_tbl = {}  # pylint: disable=protected-access

        # Sort the top-level keys to a "canonical" ordering. This should make previous patch operations look more
        # "sensible" to a human reader.
        self._sort_subtree_keys("/", TOP_LEVEL_KEY_SORT_ORDER)

        return self._v1_recipe.render(), self._msg_tbl, self._v1_recipe
