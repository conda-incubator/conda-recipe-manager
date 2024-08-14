"""
File:           recipe_graph.py
Description:    Defines a base recipe graph class. Derived classes provide initialization details.
"""

from __future__ import annotations

from networkx import DiGraph

from conda_recipe_manager.parser.recipe_parser import RecipeParser


class RecipeGraph:
    """
    Base class for all Recipe Graph types. This standardizes tooling for multiple recipe storage mechanisms.
    """

    def __init__(
        self,
        recipe_cache: dict[str, RecipeParser],
        failed_to_parse: set[str],
    ):
        """
        Constructs common types that all recipe graphs share. Derived classes handle initialization details.
        :param recipe_cache: Maps recipe file SHA-256 hashes to recipe parser instances.
        :param failed_to_parse: Set of identifiers of recipes that failed to parse.
        """
        # Cache containing parsed recipes
        self._recipe_cache = recipe_cache
        # Create a secondary :  look-up table that maps package names to hashes. This will make graph generation easier.
        self._name_to_sha256: dict[str, str] = {}
        self._unknown_package_names: set[str] = set()
        for hash, parser in self._recipe_cache.items():
            # TODO handle multi-output recipes
            # TODO improve this. Current fall-back is imperfect. Use fuzzy-matching?
            package_name = ""
            try:
                # TODO Fix: Can't currently parse the `replace()` pipe-function
                package_name = parser.get_value("/package/name", sub_vars=True)
            except Exception:
                if parser.contains_variable("name"):
                    package_name = parser.get_variable("name")
                else:
                    self._unknown_package_names.add(hash)
            self._name_to_sha256[package_name] = hash

        # Debugging info: tracks recipes that failed to parse with some kind of identifier
        self._failed_to_parse = failed_to_parse

        # TODO construct graphs
        # Dependency graph representations, built from the initial cache.
        self._build_graph = DiGraph()
        self._test_graph = DiGraph()

        for hash, parser in self._recipe_cache.items():
            # TODO handle multi-output recipes
            # TODO find build and test dependencies, use name look-up table to
            #      start building nodes by hash
            # TODO filter dependencies by section/type.
            # TODO get dependency values by section
            parser.get_dependency_paths()

    def __bool__(self) -> bool:
        """
        Indicates if the RecipeGraph contains information.
        :returns: True if the graph is "truthy" and holds information. False otherwise.
        """
        return bool(self._recipe_cache)

    def get_failed_recipe_count(self) -> int:
        """
        Provides the number of recipes that failed to parse.
        :returns: Count of recipes that failed to parse
        """
        return len(self._failed_to_parse)

    def get_total_recipe_count(self) -> int:
        """
        Calculates the total number of recipes processed (includes failures)
        :returns: Number of recipes that have been processed
        """
        return len(self._recipe_cache) + self.get_failed_recipe_count()
