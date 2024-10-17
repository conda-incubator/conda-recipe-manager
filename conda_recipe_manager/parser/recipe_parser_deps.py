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
        if len_path != _SINGLE_OUTPUT_LEN or len_path != _MULTI_OUTPUT_LEN:
            return False

        # Single-output
        if len_path == _SINGLE_OUTPUT_LEN:
            return (
                bool(path[0])
                and path[1] == "requirements"
                and str_to_dependency_section(path[2]) is not None
                and path[3].isdigit()
            )

        # Multi-output
        return (
            bool(path[0])
            and path[1] == "outputs"
            and path[2].isdigit()
            and path[3] == "requirements"
            and str_to_dependency_section(path[4]) is not None
            and path[5].isdigit()
        )

    def add_dependency(
        self, dep: Dependency, conflict_mode: DependencyConflictMode = DependencyConflictMode.REPLACE
    ) -> bool:
        """
        Convenience function that adds a dependency from a recipe file.

        :param dep: Dependency to add
        :param conflict_mode: (Optional) Indicates how duplicate dependencies should be handled. Defaults to replacing
            the existing dependency. Duplicates match by name only.
        :returns: The result of the underlying patch command, indicating that a change occurred.
        """
        # TODO add V1 support
        # Validate the Dependency, in case the user rolled-their-own.
        if not RecipeParserDeps._is_valid_dependency_path(dep.path):
            return False

        # TODO handle path does not exist -> add path
        base_path: Final[str] = dep.path.rsplit("/", 1)[0]
        patch_path = f"{base_path}/-"
        # TODO: Add a "get dependencies at path" function to `RecipeReaderDeps`
        cur_deps: Final[list[Optional[str]]] = cast(
            list[Optional[str]], self.get_value(base_path, sub_vars=True, default=[])
        )

        # Check for duplicate dependencies, if applicable.
        if conflict_mode != DependencyConflictMode.USE_BOTH:
            for i, cur_dep in enumerate(cur_deps):
                cur_dep = RecipeReaderDeps._sanitize_dep(cur_dep)
                if cur_dep is None:
                    continue

                cur_data = dependency_data_from_string(cur_dep)
                if cast(str, cur_data.name) != cast(str, dep.data.name):
                    continue

                # If we have a name match, act according to the conflict mode
                match conflict_mode:
                    case DependencyConflictMode.IGNORE:
                        return False
                    case DependencyConflictMode.REPLACE:
                        patch_path = f"{base_path}/{i}"
                        break

        return self.patch({"op": "add", "path": patch_path, "value": dependency_data_get_original_str(dep.data)})

    def rm_dependency(self, dep: Dependency) -> bool:
        """
        Convenience function that removes a dependency from a recipe file. No exceptions are thrown if the dependency
        does not exist.

        :param dep: Dependency to remove
        :returns: The result of the underlying patch command, indicating that a change occurred.
        """
        return self.patch({"op": "remove", "path": dep.path})
