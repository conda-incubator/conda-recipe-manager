"""
:Description: Provides an editing-capable variant of the RecipeReaderDeps class.
"""

from __future__ import annotations

from typing import Final, Optional, cast

from conda_recipe_manager.parser.dependency import (
    Dependency,
    DependencyConflictMode,
    dependency_data_from_string,
    dependency_data_get_original_str,
    str_to_dependency_section,
)
from conda_recipe_manager.parser.enums import SelectorConflictMode
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.recipe_reader_deps import RecipeReaderDeps

# Dependency validation constants
_SINGLE_OUTPUT_LEN: Final[int] = 4
_MULTI_OUTPUT_LEN: Final[int] = 6


class RecipeParserDeps(RecipeParser, RecipeReaderDeps):
    """
    Extension of the RecipeParser and RecipeReaderDeps classes to enables advanced dependency management abilities.

    Beware of _The Diamond Problem_. This class extends the capabilities of the `RecipeParser` class with the
    dependency tooling found in `RecipeReaderDeps`.
    """

    @staticmethod
    def _is_valid_dependency_path(dep_path: str) -> bool:
        """
        Given a string, validate that the string is a valid path to a dependency in a recipe.

        :param dep_path: Target string.
        :returns: True if the string is a valid path. False otherwise.
        """
        # TODO add V1 support
        path = dep_path.split("/")
        len_path = len(path)
        if len_path not in {_SINGLE_OUTPUT_LEN, _MULTI_OUTPUT_LEN}:
            return False

        # Single-output
        if len_path == _SINGLE_OUTPUT_LEN:
            return (
                not bool(path[0])
                and path[1] == "requirements"
                and str_to_dependency_section(path[2]) is not None
                and path[3].isdigit()
            )

        # Multi-output
        return (
            not bool(path[0])
            and path[1] == "outputs"
            and path[2].isdigit()
            and path[3] == "requirements"
            and str_to_dependency_section(path[4]) is not None
            and path[5].isdigit()
        )

    def add_dependency(
        self,
        dep: Dependency,
        dep_mode: DependencyConflictMode = DependencyConflictMode.REPLACE,
        sel_mode: SelectorConflictMode = SelectorConflictMode.REPLACE,
    ) -> bool:
        """
        Convenience function that adds a dependency to a recipe file. The `path` attribute is used to locate which
        section and output is being used, but the index position is not guaranteed, unless `EXACT_POSITION` mode is
        used.

        :param dep: Dependency to add.
        :param dep_mode: (Optional) Indicates how duplicate dependencies should be handled. Defaults to replacing the
            existing dependency. Duplicates match by name only.
        :param sel_mode: (Optional) Indicates how an existing selector should be handled. Defaults to replacing the
            existing selector.
        :returns: The result of the underlying patch command, indicating that a change occurred.
        """
        # TODO add V1 support
        # Validate the Dependency, in case the user rolled-their-own.
        if not RecipeParserDeps._is_valid_dependency_path(dep.path):
            return False

        # TODO handle path does not exist -> add path
        base_path: Final[str] = dep.path.rsplit("/", 1)[0]
        patch_path = dep.path if dep_mode == DependencyConflictMode.EXACT_POSITION else f"{base_path}/-"
        # TODO: Add a "get dependencies at path" function to `RecipeReaderDeps`
        cur_deps: Final[list[Optional[str]]] = cast(
            list[Optional[str]], self.get_value(base_path, sub_vars=True, default=[])
        )

        # Check for duplicate dependencies, if applicable.
        if dep_mode not in {DependencyConflictMode.USE_BOTH, DependencyConflictMode.EXACT_POSITION}:
            for i, cur_dep in enumerate(cur_deps):
                cur_dep = RecipeReaderDeps._sanitize_dep(cur_dep)
                if cur_dep is None:
                    continue

                cur_data = dependency_data_from_string(cur_dep)
                if cast(str, cur_data.name) != cast(str, dep.data.name):
                    continue

                # If we have a name match, act according to the conflict mode
                match dep_mode:
                    case DependencyConflictMode.IGNORE:
                        return False
                    case DependencyConflictMode.REPLACE:
                        patch_path = f"{base_path}/{i}"
                        break

        # Patch to add the dependency and apply any selectors.
        patch_success = self.patch(
            {"op": "add", "path": patch_path, "value": dependency_data_get_original_str(dep.data)}
        )
        if patch_success and dep.selector is not None:
            sel_path = patch_path
            # `add_selector()`, by nature of how selectors work, does not support "append" mode. If an append operation
            # occurred, we must calculate the position of the last array element. We only add selectors on a successful
            # patch, so we know we can make assume a dependency list exists.
            if sel_path.endswith("/-"):
                sel_path = sel_path[0:-1] + str(len(cast(list[str], self.get_value(base_path))) - 1)
            self.add_selector(sel_path, dep.selector, mode=sel_mode)
        return patch_success

    def remove_dependency(self, dep: Dependency) -> bool:
        """
        Convenience function that removes a dependency from a recipe file. No exceptions are thrown if the dependency
        does not exist.

        :param dep: Dependency to remove
        :returns: The result of the underlying patch command, indicating that a change occurred.
        """
        return self.patch({"op": "remove", "path": dep.path})
