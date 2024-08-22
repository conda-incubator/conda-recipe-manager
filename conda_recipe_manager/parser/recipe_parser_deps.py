"""
:Description: Provides a subclass of RecipeParser that adds advanced dependency management tools.
"""

from __future__ import annotations

from typing import Final, Optional, cast

from conda.models.match_spec import MatchSpec

from conda_recipe_manager.parser._types import ROOT_NODE_VALUE
from conda_recipe_manager.parser.dependency import Dependency, DependencyMap, str_to_dependency_section
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.selector_parser import SelectorParser
from conda_recipe_manager.parser.types import SchemaVersion


class RecipeParserDeps(RecipeParser):
    """
    Extension of the base RecipeParser class to enables advanced dependency management abilities. The base RecipeParser
    class is so large, that this has been broken-out for maintenance purposes.
    """

    @staticmethod
    def _add_top_level_dependencies(root_package: str, dep_map: DependencyMap) -> None:
        """
        Helper function that applies "root"/top-level dependencies to packages in multi-output recipes.
        """
        if len(dep_map) <= 1 or root_package not in dep_map:
            return
        root_dependencies: Final[list[Dependency]] = dep_map[root_package]
        for package in dep_map:
            if package == root_package:
                continue
            # Change the "required_by" package name to the current package, not the root package name.
            dep_map[package].extend(
                [Dependency(package, d.path, d.type, d.match_spec, d.selector) for d in root_dependencies]
            )

    def _fetch_optional_selector(self, path: str) -> Optional[SelectorParser]:
        """
        Given a recipe path, optionally return a SelectorParser object.

        :param path: Path to the target value
        :returns: A parsed selector, if one is available. Otherwise, None.
        """
        try:
            return SelectorParser(self.get_selector_at_path(path), self._schema_version)
        except KeyError:
            return None

    def get_package_names_to_path(self) -> dict[str, str]:
        """
        Get a map containing all the packages (artifacts) named in a recipe to their paths in the recipe structure.

        :raises KeyError: If a package in the recipe does not have a name
        :raises ValueError: If a recipe contains a package with duplicate names
        :returns: Mapping of package name to path where that package is found
        """
        # TODO Figure out: Skip top-level packages for multi-output recipe files?
        package_tbl: dict[str, str] = {}
        root_name_path: Final[str] = (
            "/recipe/name" if self.is_multi_output() and self._schema_version == SchemaVersion.V1 else "/package/name"
        )
        name_path: Final[str] = (
            "/package/name" if self.is_multi_output() and self._schema_version == SchemaVersion.V1 else "/name"
        )
        for path in self.get_package_paths():
            try:
                if path == ROOT_NODE_VALUE:
                    name = cast(str, self.get_value(root_name_path, sub_vars=True))
                else:
                    name = cast(str, self.get_value(RecipeParser.append_to_path(path, name_path), sub_vars=True))
            except KeyError as e:
                raise KeyError(f"Could not find a package name associated with path: {path}") from e

            if name in package_tbl:
                raise ValueError(f"Duplicate package name found: {name}")

            package_tbl[name] = path
        return package_tbl

    def get_all_dependencies(self) -> DependencyMap:
        """
        Get a parsed representation of all the dependencies found in the recipe.

        :raises KeyError: If a package in the recipe does not have a name
        :raises ValueError: If a recipe contains a package with duplicate names
        :returns: A structured representation of the dependencies.
        """
        # TODO Figure out: Skip top-level packages for multi-output recipe files?
        package_path_tbl: Final[dict[str, str]] = self.get_package_names_to_path()
        root_package = ""
        dep_map: DependencyMap = {}

        for package, path in package_path_tbl.items():
            if path == ROOT_NODE_VALUE:
                root_package = package

            requirements = cast(
                dict[str, list[str]],
                self.get_value(RecipeParser.append_to_path(path, "/requirements"), default=[], sub_vars=True),
            )
            dep_map[package] = []
            for section_str, deps in requirements.items():
                section = str_to_dependency_section(section_str)
                # Unrecognized sections will be skipped as "junk" data
                if section is None:
                    continue

                for i, dep in enumerate(deps):
                    # NOTE: `get_dependency_paths()` uses the same approach for calculating dependency paths.
                    dep_path = RecipeParser.append_to_path(path, f"/requirements/{section_str}/{i}")
                    dep_map[package].append(
                        Dependency(
                            required_by=package,
                            path=dep_path,
                            type=section,
                            match_spec=MatchSpec(dep),
                            selector=self._fetch_optional_selector(dep_path),
                        )
                    )

        # Apply top-level dependencies to multi-output recipe packages
        RecipeParserDeps._add_top_level_dependencies(root_package, dep_map)

        return dep_map
