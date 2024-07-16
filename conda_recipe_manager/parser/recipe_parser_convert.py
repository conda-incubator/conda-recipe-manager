"""
File:           recipe_parser_convert.py
Description:    Provides a subclass of RecipeParser that performs the conversion of a v0 recipe to the new v1 recipe
                format. This tooling was originally part of the base class, but was broken-out for easier/cleaner code
                maintenance.
"""

from __future__ import annotations

from typing import Final, Optional, cast

from conda_recipe_manager.licenses.spdx_utils import SpdxUtils
from conda_recipe_manager.parser._node import Node
from conda_recipe_manager.parser._traverse import traverse
from conda_recipe_manager.parser._types import (
    ROOT_NODE_VALUE,
    TOP_LEVEL_KEY_SORT_ORDER,
    V1_BUILD_SECTION_KEY_SORT_ORDER,
    V1_PYTHON_TEST_KEY_SORT_ORDER,
    V1_SOURCE_SECTION_KEY_SORT_ORDER,
    Regex,
)
from conda_recipe_manager.parser._utils import (
    search_any_regex,
    set_key_conditionally,
    stack_path_to_str,
    str_to_stack_path,
)
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.types import CURRENT_RECIPE_SCHEMA_FORMAT, MessageCategory, MessageTable
from conda_recipe_manager.types import JsonPatchType, JsonType, Primitives, SentinelType


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

        self._spdx_utils = SpdxUtils()
        self._msg_tbl = MessageTable()

    ## Patch utility functions ##

    def _patch_and_log(self, patch: JsonPatchType) -> bool:
        """
        Convenience function that logs failed patches to the message table.
        :param patch: Patch operation to perform
        :returns: Forwards patch results for further logging/error handling
        """
        result: Final[bool] = self._v1_recipe.patch(patch)
        if not result:
            self._msg_tbl.add_message(MessageCategory.ERROR, f"Failed to patch: {patch}")
        return result

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
            `/build/missing_dso_whitelist` -> `/build/dynamic_linking/missing_dso_allowlist`
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

    def _patch_deprecated_fields(self, base_path: str, fields: list[str]) -> None:
        """
        Automatically deprecates fields found in a common path.
        :param base_path: Shared base path where fields can be found
        :param fields: List of deprecated fields
        """
        for field in fields:
            path = RecipeParser.append_to_path(base_path, field)
            if not self._v1_recipe.contains_value(path):
                continue
            if self._patch_and_log({"op": "remove", "path": path}):
                self._msg_tbl.add_message(MessageCategory.WARNING, f"Field at `{path}` is no longer supported.")

    def _sort_subtree_keys(self, sort_path: str, tbl: dict[str, int], rename: str = "") -> None:
        """
        Convenience function that sorts 1 level of keys, given a path. Optionally allows renaming of the target node.
        No changes are made if the path provided is invalid/does not exist.
        :param sort_path: Top-level path to target sorting of child keys
        :param tbl: Table describing how keys should be sorted. Lower-value key names appear towards the top of the list
        :param rename: (Optional) If specified, renames the top-level key
        """

        def _comparison(n: Node) -> int:
            return RecipeParser._canonical_sort_keys_comparison(n, tbl)

        node = traverse(self._v1_recipe._root, str_to_stack_path(sort_path))  # pylint: disable=protected-access
        if node is None:
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
        context_obj: dict[str, Primitives] = {}
        for name, value in self._v1_recipe._vars_tbl.items():  # pylint: disable=protected-access
            # Filter-out any value not covered in the V1 format
            if not isinstance(value, (str, int, float, bool)):
                self._msg_tbl.add_message(MessageCategory.WARNING, f"The variable `{name}` is an unsupported type.")
                continue
            # Function calls need to preserve JINJA escaping or else they turn into unevaluated strings.
            if isinstance(value, str) and search_any_regex(Regex.JINJA_FUNCTIONS_SET, value):
                value = "{{" + value + "}}"
            context_obj[name] = value
        # Ensure that we do not include an empty context object (which is forbidden by the schema).
        if context_obj:
            self._patch_and_log({"op": "add", "path": "/context", "value": cast(JsonType, context_obj)})

        # Similarly, patch-in the new `schema_version` value to the top of the file
        self._patch_and_log({"op": "add", "path": "/schema_version", "value": CURRENT_RECIPE_SCHEMA_FORMAT})

        # Swap all JINJA to use the new `${{ }}` format. A `set` is used as `str.replace()` will replace all instances
        # and a value containing multiple variables could be visited multiple times, causing multiple `${{}}`
        # encapsulations.
        jinja_sub_locations: Final[set[str]] = set(self._v1_recipe.search(Regex.JINJA_SUB))
        for path in jinja_sub_locations:
            value = self._v1_recipe.get_value(path)
            # Values that match the regex should only be strings. This prevents crashes that should not occur.
            if not isinstance(value, str):
                self._msg_tbl.add_message(
                    MessageCategory.WARNING, f"A non-string value was found as a JINJA substitution: {value}"
                )
                continue
            # Safely replace `{{` but not any existing `${{` instances
            value = Regex.JINJA_REPLACE_V0_STARTING_MARKER.sub("${{", value)
            self._patch_and_log({"op": "replace", "path": path, "value": value})

    def _upgrade_selectors_to_conditionals(self) -> None:
        """
        Upgrades the proprietary comment-based selector syntax to equivalent conditional logic statements.

        TODO warn if selector is unrecognized? See list:
          https://prefix-dev.github.io/rattler-build/latest/selectors/#available-variables
        conda docs for common selectors:
          https://docs.conda.io/projects/conda-build/en/latest/resources/define-metadata.html#preprocessing-selectors
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

                # Some commonly used selectors (like `py<36`) need to be upgraded. Otherwise, these expressions will be
                # interpreted as strings. See this CEP PR for more details: https://github.com/conda/ceps/pull/71
                bool_expression = Regex.SELECTOR_PYTHON_VERSION_REPLACEMENT.sub(
                    r'match(python, "\1\2.\3")', bool_expression
                )
                # Upgrades for less common `py36` and `not py27` selectors
                bool_expression = Regex.SELECTOR_PYTHON_VERSION_EQ_REPLACEMENT.sub(
                    r'match(python, "==\1.\2")', bool_expression
                )
                bool_expression = Regex.SELECTOR_PYTHON_VERSION_NE_REPLACEMENT.sub(
                    r'match(python, "!=\1.\2")', bool_expression
                )
                # Upgrades for less common `py2k` and `py3k` selectors
                bool_expression = Regex.SELECTOR_PYTHON_VERSION_PY2K_REPLACEMENT.sub(
                    r'match(python, ">=2,<3")', bool_expression
                )
                bool_expression = Regex.SELECTOR_PYTHON_VERSION_PY3K_REPLACEMENT.sub(
                    r'match(python, ">=3,<4")', bool_expression
                )

                # TODO other common selectors to support:
                # - GPU variants (see pytorch and llama.cpp feedstocks)

                # For now, if a selector lands on a boolean value, use a ternary statement. Otherwise use the
                # conditional logic.
                patch: JsonPatchType = {
                    "op": "replace",
                    "path": selector_path,
                    "value": "${{ true if " + bool_expression + " }}",
                }
                # `skip` is special and can be a single boolean expression or a list of boolean expressions.
                if selector_path.endswith("/build/skip"):
                    patch["value"] = bool_expression
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

    def _correct_common_misspellings(self, base_package_paths: list[str]) -> None:
        """
        Corrects common spelling mistakes in field names.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        for base_path in base_package_paths:
            build_path = RecipeParser.append_to_path(base_path, "/build")
            # "If I had a nickel for every time `skip` was misspelled, I would have several nickels. Which isn't a lot,
            #  but it is weird that it has happened multiple times."
            #                                                             - Dr. Doofenshmirtz, probably
            self._patch_move_base_path(build_path, "skipt", "skip")
            self._patch_move_base_path(build_path, "skips", "skip")
            self._patch_move_base_path(build_path, "Skip", "skip")

            # `/extras` -> `/extra`
            self._patch_move_base_path(base_path, "extras", "extra")

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

                # `git` source transformations (`conda` does not appear to support all of the new features)
                self._patch_move_base_path(src_path, "/git_url", "/git")
                self._patch_move_base_path(src_path, "/git_tag", "/tag")
                self._patch_move_base_path(src_path, "/git_rev", "/rev")
                self._patch_move_base_path(src_path, "/git_depth", "/depth")

                # Canonically sort this section
                self._sort_subtree_keys(src_path, V1_SOURCE_SECTION_KEY_SORT_ORDER)

    def _upgrade_build_script_section(self, build_path: str) -> None:
        """
        Upgrades the `/build/script` section if needed. Some fields like `script_env` will need to be wrapped into a new
        `Script` object. Simple `script` sections can be left unchanged.
        :param build_path: Build section path to upgrade
        """
        script_env_path: Final[str] = RecipeParser.append_to_path(build_path, "/script_env")
        # The environment list could contain dictionaries if the variables are conditionally included.
        script_env_lst: Final[list[str | dict[str, str]]] = cast(
            list[str | dict[str, str]], self._v1_recipe.get_value(script_env_path, [])
        )
        if not script_env_lst:
            return

        script_path: Final[str] = RecipeParser.append_to_path(build_path, "/script")
        new_script_obj: JsonType = {}
        # Set environment variables need to be parsed and then re-added as a dictionary. Unset variables are listed
        # in the `secrets` section.
        new_env: dict[str, str] = {}
        new_secrets: list[str | dict[str, str]] = []
        for item in script_env_lst:
            # Attempt to edit conditional variables
            if isinstance(item, dict):
                if "then" not in item:
                    self._msg_tbl.add_message(
                        MessageCategory.ERROR, f"Could not parse dictionary `{item}` found in {script_env_path}"
                    )
                    continue
                tokens = [i.strip() for i in item["then"].split("=")]
                if len(tokens) == 1:
                    new_secrets.append(item)
                else:
                    # The spec does not support conditional statements in a dictionary. As per discussions with the
                    # community, the best course of action is manual intervention.
                    self._msg_tbl.add_message(
                        MessageCategory.ERROR,
                        f"Converting `{item}` found in {script_env_path} is not supported."
                        " Manually replace the selector with a `cmp()` function.",
                    )
                continue

            tokens = [i.strip() for i in item.split("=")]
            if len(tokens) == 1:
                new_secrets.append(tokens[0])
            elif len(tokens) == 2:
                new_env[tokens[0]] = tokens[1]
            else:
                self._msg_tbl.add_message(MessageCategory.ERROR, f"Could not parse `{item}` found in {script_env_path}")

        set_key_conditionally(cast(dict[str, JsonType], new_script_obj), "env", cast(JsonType, new_env))
        set_key_conditionally(cast(dict[str, JsonType], new_script_obj), "secrets", cast(JsonType, new_secrets))

        script_value = self._v1_recipe.get_value(script_path, "")
        patch_op: Final[str] = "replace" if script_value else "add"
        # TODO: Simple script files should be set as `file` not `content`
        set_key_conditionally(cast(dict[str, JsonType], new_script_obj), "content", script_value)

        self._patch_and_log({"op": patch_op, "path": script_path, "value": new_script_obj})
        self._patch_and_log({"op": "remove", "path": script_env_path})

    def _upgrade_build_section(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts the `build` section(s) of a recipe file.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        build_deprecated: Final[list[str]] = [
            "pre-link",
            "noarch_python",
            "features",
            "msvc_compiler",
            "requires_features",
            "provides_features",
            "preferred_env",
            "preferred_env_executable_paths",
            "disable_pip",
            "pin_depends",
            "overlinking_ignore_patterns",
            "rpaths_patcher",
            "post-link",
            "pre-unlink",
            "pre-link",
        ]

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
            if self._v1_recipe.contains_value(old_ire_path):
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

            # New `prefix_detection` section changes
            # NOTE: There is a new `force_file_type` field that may map to an unknown field that conda supports.
            self._patch_move_new_path(build_path, "/ignore_prefix_files", "/prefix_detection", "/ignore")
            self._patch_move_new_path(
                build_path, "/detect_binary_files_with_prefix", "/prefix_detection", "/ignore_binary_files"
            )

            # New `dynamic_linking` section changes
            # NOTE: `overdepending_behavior` and `overlinking_behavior` are new fields that don't have a direct path
            #       to conversion.
            self._patch_move_new_path(build_path, "/rpaths", "/dynamic_linking", "/rpaths")
            self._patch_move_new_path(build_path, "/binary_relocation", "/dynamic_linking", "/binary_relocation")
            self._patch_move_new_path(
                build_path, "/missing_dso_whitelist", "/dynamic_linking", "/missing_dso_allowlist"
            )
            self._patch_move_new_path(build_path, "/runpath_whitelist", "/dynamic_linking", "/rpath_allowlist")

            self._upgrade_build_script_section(build_path)
            self._patch_deprecated_fields(build_path, build_deprecated)

            # Canonically sort this section
            self._sort_subtree_keys(build_path, V1_BUILD_SECTION_KEY_SORT_ORDER)

    def _upgrade_requirements_section(self, base_package_paths: list[str]) -> None:
        """
        Upgrades/converts the `requirements` section(s) of a recipe file.
        :param base_package_paths: Set of base paths to process that could contain this section.
        """
        for base_path in base_package_paths:
            requirements_path = RecipeParser.append_to_path(base_path, "/requirements")
            if not self._v1_recipe.contains_value(requirements_path):
                continue

            # Simple transformations
            self._patch_move_base_path(requirements_path, "/run_constrained", "/run_constraints")

    def _fix_bad_licenses(self, about_path: str) -> None:
        """
        Attempt to correct licenses to match SPDX-recognized names.

        For now, this does not call-out to an SPDX database. Instead, we attempt to correct common mistakes.
        :param about_path: Path to the `about` section, where the `license` field is located.
        """
        license_path: Final[str] = RecipeParser.append_to_path(about_path, "/license")
        old_license: Final[Optional[str]] = cast(Optional[str], self._v1_recipe.get_value(license_path, default=None))
        if old_license is None:
            self._msg_tbl.add_message(MessageCategory.WARNING, f"No `license` provided in `{about_path}`")
            return

        corrected_license: Final[Optional[str]] = self._spdx_utils.find_closest_license_match(old_license)

        if corrected_license is None:
            self._msg_tbl.add_message(MessageCategory.WARNING, f"Could not patch unrecognized license: `{old_license}`")
            return

        # If it ain't broke, don't patch it
        if old_license == corrected_license:
            return

        # Alert the user that a patch was made, in case it needs manual verification. This warning will not emit if
        # the patch failed (failure will generate an arguably more important message)
        if self._patch_and_log({"op": "replace", "path": license_path, "value": corrected_license}):
            self._msg_tbl.add_message(
                MessageCategory.WARNING, f"Changed {license_path} from `{old_license}` to `{corrected_license}`"
            )

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

            self._fix_bad_licenses(about_path)

            # R packages like to use multiline strings without multiline markers, which get interpreted as list members
            # TODO address this at parse-time, adding a new multiline mode
            summary_path = RecipeParser.append_to_path(about_path, "/summary")
            summary = self._v1_recipe.get_value(summary_path, "")
            if isinstance(summary, list):
                self._patch_and_log(
                    {"op": "replace", "path": summary_path, "value": "\n".join(cast(list[str], summary))}
                )

            # Remove deprecated `about` fields
            self._patch_deprecated_fields(about_path, about_deprecated)

    def _upgrade_test_pip_check(self, base_path: str, test_path: str) -> None:
        """
        Replaces the commonly used `pip check` test-case with the new `python/pip_check` attribute, if applicable.
        :param base_path: Base path for the build target to upgrade
        :param test_path: Test path for the build target to upgrade
        """
        pip_check_variants: Final[set[str]] = {
            "pip check",
            "python -m pip check",
            "python3 -m pip check",
        }
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
            # TODO Future: handle selector cases (pip check will be in the `then` section of a dictionary object)
            if not isinstance(command, str) or command not in pip_check_variants:
                continue
            # For now, we will only patch-out the first instance when no selector is attached
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

            # Canonically sort the python section, if it exists
            self._sort_subtree_keys(RecipeParser.append_to_path(test_path, "/python"), V1_PYTHON_TEST_KEY_SORT_ORDER)

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
        # Some recipes use `foo.<function()>` instead of `{{ foo | <function()> }}` in JINJA statements. This causes
        # rattler-build to fail with `invalid operation: object has no method named <function()>`
        # NOTE: This is currently done BEFORE converting to use `env.get()` to wipe-out those changes.
        content = Regex.PRE_PROCESS_JINJA_DOT_FUNCTION_IN_ASSIGNMENT.sub(r"\1 | \2", content)
        content = Regex.PRE_PROCESS_JINJA_DOT_FUNCTION_IN_SUBSTITUTION.sub(r"\1 | \2", content)
        # Strip any problematic parenthesis that may be left over from the previous operations.
        content = Regex.PRE_PROCESS_JINJA_DOT_FUNCTION_STRIP_EMPTY_PARENTHESIS.sub(r"\1", content)
        # Attempt to normalize quoted multiline strings into the common `|` syntax.
        # TODO: Handle multiple escaped newlines (very uncommon)
        content = Regex.PRE_PROCESS_QUOTED_MULTILINE_STRINGS.sub(r"\1\2: |\1  \3\1  \4", content)

        # rattler-build@0.18.0: Introduced checks for deprecated `max_pin` and `min_pin` fields. This replacement
        # addresses the change in numerous JINJA functions that use this nomenclature.
        content = Regex.PRE_PROCESS_MIN_PIN_REPLACEMENT.sub("lower_bound=", content)
        content = Regex.PRE_PROCESS_MAX_PIN_REPLACEMENT.sub("upper_bound=", content)

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

        # Replace `{{ hash_type }}:` with the value of `hash_type`, which is likely `sha256`. This is an uncommon
        # practice that is not part of the V1 specification. Currently, about 70 AnacondaRecipes and conda-forge files
        # do this in our integration testing sample.
        hash_type_var_variants: Final[set[str]] = {
            '{% set hash_type = "sha256" %}\n',
            '{% set hashtype = "sha256" %}\n',
            '{% set hash = "sha256" %}\n',  # NOTE: `hash` is also commonly used for the actual SHA-256 hash value
        }
        for hash_type_variant in hash_type_var_variants:
            content = content.replace(hash_type_variant, "")
        content = Regex.PRE_PROCESS_JINJA_HASH_TYPE_KEY.sub("sha256:", content)

        return content

    def render_to_v1_recipe_format(self) -> tuple[str, MessageTable, str]:
        """
        Takes the current recipe representation and renders it to the V1 format WITHOUT modifying the current recipe
        state.

        This "new" format is defined in the following CEPs:
          - https://github.com/conda-incubator/ceps/blob/main/cep-13.md
          - https://github.com/conda-incubator/ceps/blob/main/cep-14.md

        :returns: Returns a tuple containing:
            - The converted recipe, as a string
            - A `MessageTbl` instance that contains error logging
            - Converted recipe file debug string. USE FOR DEBUGGING PURPOSES ONLY!
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

        # There are a number of recipe files that contain the same misspellings. This is an attempt to
        # solve the more common issues.
        self._correct_common_misspellings(base_package_paths)

        # Upgrade common sections found in a recipe
        self._upgrade_source_section(base_package_paths)
        self._upgrade_build_section(base_package_paths)
        self._upgrade_requirements_section(base_package_paths)
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

        return self._v1_recipe.render(), self._msg_tbl, str(self._v1_recipe)
