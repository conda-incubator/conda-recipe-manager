"""
:Description: CLI understanding recipe dependency graphs.
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path
from typing import Final

import click

from conda_recipe_manager.commands.utils.print import print_err
from conda_recipe_manager.grapher.recipe_graph import PackageStats, RecipeGraph
from conda_recipe_manager.grapher.recipe_graph_from_disk import RecipeGraphFromDisk


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

    # TODO implement CLI
    # recipe_graph.plot()
