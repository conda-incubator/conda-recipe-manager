"""
File:           recipe_parser_convert.py
Description:    Provides a subclass of RecipeParser that performs the conversion of a v0 recipe to the new v1 recipe
                format. This tooling was originally part of the base class, but was broken-out for easier/cleaner code
                maintenance.
"""
from __future__ import annotations

from typing import Final, cast

from conda_recipe_manager.parser._node import Node
from conda_recipe_manager.parser._traverse import traverse
from conda_recipe_manager.parser._types import (
    ROOT_NODE_VALUE,
    TOP_LEVEL_KEY_SORT_ORDER,
    V1_BUILD_SECTION_KEY_SORT_ORDER,
    Regex,
)
from conda_recipe_manager.parser._utils import stack_path_to_str, str_to_stack_path
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.types import CURRENT_RECIPE_SCHEMA_FORMAT, MessageCategory, MessageTable
from conda_recipe_manager.types import JsonPatchType, JsonType, SentinelType


class RecipeParserConvert(RecipeParser):
    """
    Extension of the base RecipeParser class to enables upgrading recipes from the old to new format.
    This was originally part of the RecipeParser class but was broken-out for easier maintenance.
    """

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

        ## JINJA -> `context` object ##

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

        ## Convert selectors into ternary statements or `if` blocks ##
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
                        "value": cast(JsonType, bool_object),
                    }
                # Apply the patch
                _patch_and_log(patch)
                new_recipe.remove_selector(selector_path)

        # Cached copy of all of the "outputs" in a recipe. This is useful for easily handling multi and single output
        # recipes in 1 loop construct.
        base_package_paths: Final[list[str]] = new_recipe.get_package_paths()

        # TODO Fix: comments are not preserved with patch operations (add a flag to `patch()`?)

        ## `build` section changes and validation ##

        for base_path in base_package_paths:
            # Move `run_exports` and `ignore_run_exports` from `build` to `requirements`

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

            # Perform internal section changes per `build/` section
            build_path = RecipeParser.append_to_path(base_path, "/build")
            if not new_recipe.contains_value(build_path):
                continue

            # `build/entry_points` -> `build/python/entry_points`
            if new_recipe.contains_value(RecipeParser.append_to_path(build_path, "/entry_points")):
                _patch_add_missing_path(build_path, "/python")
            _patch_move_base_path(build_path, "/entry_points", "/python/entry_points")

            # Canonically sort this section
            _sort_subtree_keys(build_path, V1_BUILD_SECTION_KEY_SORT_ORDER)

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

        ## `test` section changes and upgrades ##

        # NOTE: For now, we assume that the existing test section comprises of a single test entity. Developers will
        # have to use their best judgement to manually break-up the test into multiple tests as they see fit.
        for base_path in base_package_paths:
            test_path = RecipeParser.append_to_path(base_path, "/test")
            if not new_recipe.contains_value(test_path):
                continue

            # Moving `files` to `files/recipe` is not possible in a single `move` operation as a new path has to be
            # created in the path being moved.
            test_files_path = RecipeParser.append_to_path(test_path, "/files")
            if new_recipe.contains_value(test_files_path):
                test_files_value = new_recipe.get_value(test_files_path)
                # TODO: Fix, replace does not work here, produces `- null`, Issue #20
                # _patch_and_log({"op": "replace", "path": test_files_path, "value": None})
                _patch_and_log({"op": "remove", "path": test_files_path})
                _patch_and_log({"op": "add", "path": test_files_path, "value": None})
                _patch_and_log(
                    {
                        "op": "add",
                        "path": RecipeParser.append_to_path(test_files_path, "/recipe"),
                        "value": test_files_value,
                    }
                )
            # Edge case: `/source_files` exists but `/files` does not
            elif new_recipe.contains_value(RecipeParser.append_to_path(test_path, "/source_files")):
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
                {"op": "add", "path": RecipeParser.append_to_path(test_path, "/python/pip_check"), "value": pip_check}
            )

            _patch_move_base_path(test_path, "/commands", "/script")
            _patch_move_base_path(test_path, "/imports", "/python/imports")
            _patch_move_base_path(test_path, "/downstreams", "/downstream")

            # Move `test` to `tests` and encapsulate the pre-existing object into a list
            new_test_path = f"{test_path}s"
            test_element = cast(dict[str, JsonType], new_recipe.get_value(test_path))
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
            _patch_and_log({"op": "add", "path": new_test_path, "value": test_array})
            _patch_and_log({"op": "remove", "path": test_path})

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
