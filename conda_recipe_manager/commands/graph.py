"""
:Description: CLI understanding recipe dependency graphs.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path
from typing import Final

import click

from conda_recipe_manager.commands.utils.print import print_err
from conda_recipe_manager.grapher.recipe_graph import PackageStats, RecipeGraph
from conda_recipe_manager.grapher.recipe_graph_from_disk import RecipeGraphFromDisk
from conda_recipe_manager.grapher.types import GraphType, PackageStatsEncoder


@click.command(short_help="")
@click.argument("path", type=click.Path(exists=True, path_type=Path, file_okay=False))  # type: ignore[misc]
def graph(path: Path) -> None:
    """
    Interactive CLI that provides tools for examining a dependency graph created from conda recipes.

    Arguments:
      PATH - A path containing recipe files to be examined.
    """
    print("Constructing dependency graph...")
    start_time: Final[float] = time.time()

    # TODO error on empty graph
    recipe_graph: Final[RecipeGraph] = RecipeGraphFromDisk(path)
    if not recipe_graph:
        print_err(f"The path provided does not contain any recipe files: {path}")
        # TODO use enum scheme
        sys.exit(1)

    total_time: Final[float] = time.time() - start_time
    package_stats: Final[PackageStats] = recipe_graph.get_package_stats()
    failed_count: Final[int] = len(package_stats.recipes_failed_to_parse)
    success_rate: Final[float] = (1 - (failed_count / package_stats.total_recipes)) * 100
    print(
        f"Failed to parse {failed_count}"
        f" of {package_stats.total_recipes} recipe files ({success_rate:.2f}% success)."
    )
    # NOTE: There is no stdlib way to recursively calculate an object's memory usage.
    print(f"Estimated memory usage of the graph: {len(pickle.dumps(recipe_graph)) / (2**20):.2f}MiB")
    print(f"Total graph construction time: {round(total_time, 2)}s")

    print()
    print("== Main menu ==")
    while True:
        command = input("> ").lower()
        match command.split():
            case ["help"] | ["h"]:
                print(
                    "Conda Recipe Manager (CRM) Graph Utility Interactive Shell (GUIS)\n\n"
                    "Use exit, q, or Ctrl-D to quit.\n\n"
                    "Commands:\n"
                    "  - plot (build|test) (package|all)\n"
                    "    Generates a visual representation of the requested dependency graph.\n"
                    "    Using `all` prints the entire graph.\n"
                    "  - stats\n"
                    "    Prints graph construction statistics.\n"
                    "  - help\n"
                    "    Prints this help message.\n"
                )
            case ["plot", g_type, pkg]:
                if g_type not in GraphType:
                    print(f"Unrecognized graph type: {g_type}")
                    continue
                if pkg == "all":
                    recipe_graph.plot(GraphType(g_type))
                    continue
                # TODO add package-name check
                if not recipe_graph.contains_package_name(pkg):
                    print(f"Package not found: {pkg}")
                    continue
                recipe_graph.plot(GraphType(g_type), pkg)
            case ["stats"] | ["statistics"]:
                print(json.dumps(package_stats, indent=2, sort_keys=True, cls=PackageStatsEncoder))
            case ["exit"] | ["esc"] | ["quit"] | ["q"]:
                print("Closing interactive menu...")
                break
            case _:
                print("Invalid command.")
