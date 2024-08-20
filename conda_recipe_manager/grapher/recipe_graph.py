"""
:Description: Defines a base recipe graph class. Derived classes provide initialization details.
"""

from __future__ import annotations

from typing import Final, cast

import matplotlib.pyplot as plt
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout

from conda_recipe_manager.grapher.types import GraphType, PackageStats
from conda_recipe_manager.parser.dependency import DependencySection
from conda_recipe_manager.parser.recipe_parser_deps import RecipeParserDeps


class RecipeGraph:
    """
    Base class for all Recipe Graph types. This standardizes tooling for multiple recipe storage mechanisms.
    """

    def __init__(
        self,
        recipe_cache: dict[str, RecipeParserDeps],
        recipes_failed_to_parse: set[str],
    ):
        """
        Constructs common types that all recipe graphs share. Derived classes handle initialization details.

        :param recipe_cache: Maps recipe file SHA-256 hashes to recipe parser instances.
        :param recipes_failed_to_parse: Set of identifiers of recipes that failed to parse.
        """
        self._package_stats = PackageStats(
            recipes_failed_to_parse=recipes_failed_to_parse,
            total_parsed_recipes=len(recipe_cache),
            total_recipes=len(recipe_cache) + len(recipes_failed_to_parse),
        )

        # Cache containing parsed recipes
        self._recipe_cache = recipe_cache
        # Create a secondary :  look-up table that maps package names to hashes. This will make graph generation easier.
        self._name_to_sha256: dict[str, str] = {}
        for sha, parser in self._recipe_cache.items():
            # TODO handle multi-output recipes
            # TODO improve this. Current fall-back is imperfect. Use fuzzy-matching?
            package_name = ""
            try:
                # TODO Fix: Can't currently parse the `replace()` pipe-function
                package_name = cast(str, parser.get_value("/package/name", sub_vars=True))
            except KeyError:
                if parser.contains_variable("name"):
                    package_name = cast(str, parser.get_variable("name"))
                else:
                    self._package_stats.recipes_of_unknown_packages.add(sha)
            self._name_to_sha256[package_name] = sha

        # TODO construct graphs
        # Dependency graph representations, built from the initial cache.
        self._build_graph = nx.DiGraph()
        self._test_graph = nx.DiGraph()

        for sha, parser in self._recipe_cache.items():
            # TODO handle multi-output recipes
            # TODO find build and test dependencies, use name look-up table to
            #      start building nodes by hash
            # TODO filter dependencies by section/type.
            # TODO get dependency values by section
            # TODO fix MatchSpec blowing up on failed sub_vars
            try:
                dep_map = parser.get_all_dependencies()
            except Exception:  # pylint: disable=broad-exception-caught
                self._package_stats.recipes_failed_to_parse_dependencies.add(sha)
                continue

            for package_name, deps in dep_map.items():
                self._package_stats.total_packages += 1
                for dep in deps:
                    match dep.type:
                        # Build graph
                        case DependencySection.BUILD | DependencySection.HOST:
                            # TODO use hash/UID?
                            self._build_graph.add_edge(package_name, dep.match_spec.name)

                        # Test graph
                        # TODO does this include run constraints?
                        case DependencySection.RUN | DependencySection.TEST:
                            self._test_graph.add_edge(package_name, dep.match_spec.name)

    def __bool__(self) -> bool:
        """
        Indicates if the RecipeGraph contains information.

        :returns: True if the graph is "truthy" and holds information. False otherwise.
        """
        return bool(self._recipe_cache)

    def get_package_stats(self) -> PackageStats:
        """
        Returns a structure filled with package statistics gathered during graph constructed.

        :returns: A structure of package-related statistics
        """
        return self._package_stats

    def plot(self, graph_type: GraphType) -> None:
        """
        Draws a dependency graph to the screen.

        :param graph_type: Indicates which kind of graph to render
        """

        def _get_graph() -> nx.Digraph:
            match graph_type:
                case GraphType.BUILD:
                    return self._build_graph
                case GraphType.TEST:
                    return self._test_graph

        graph_to_render: Final[nx.DiGraph] = _get_graph()

        # TODO add blocking flag?
        # TODO add enum for which graph

        plt.figure()
        # TODO Fix this later
        # plt.title(f"{name}@{version} on TODO")
        plt.axis("off")
        nx.draw(
            graph_to_render,
            pos=graphviz_layout(graph_to_render, "dot"),
            # node_size=2000,
            # labels=label_map,
            # with_labels=True,
            alpha=0.6,
        )
        plt.show()
