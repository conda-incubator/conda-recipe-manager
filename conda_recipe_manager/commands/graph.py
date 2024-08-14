"""
File:           graph.py
Description:    CLI understanding recipe dependency graphs.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Final

import click

from conda_recipe_manager.commands.utils.print import print_err
from conda_recipe_manager.grapher.recipe_graph import RecipeGraph
from conda_recipe_manager.grapher.recipe_graph_from_disk import RecipeGraphFromDisk


@click.command(short_help="")
@click.argument("path", type=click.Path(exists=True, path_type=Path, file_okay=False))  # type: ignore[misc]
def graph(path: Path) -> None:
    """
    Provides dependency graphing tools. TODO more description
    """
    start_time: Final[float] = time.time()

    # TODO error on empty graph
    recipe_graph: Final[RecipeGraph] = RecipeGraphFromDisk(path)
    if not recipe_graph:
        print_err(f"The path provided does not contain any recipe files: {path}")
        # TODO use enum scheme
        sys.exit(1)

    total_time: Final[float] = time.time() - start_time
    failed_count: Final[int] = recipe_graph.get_failed_recipe_count()
    total_count: Final[int] = recipe_graph.get_total_recipe_count()
    success_rate: Final[float] = (1 - round(failed_count / total_count, 4)) * 100
    print(f"Failed to parse {failed_count}" f" of {total_count} recipe files ({success_rate}% success).")
    print(f"Total execution time: {round(total_time, 2)}s")
