"""
:Description: Base CLI for all `conda-recipe-manager` commands
"""

from __future__ import annotations

import click

from conda_recipe_manager.commands.convert import convert
from conda_recipe_manager.commands.dep_scanner import dep_scanner
from conda_recipe_manager.commands.graph import graph
from conda_recipe_manager.commands.rattler_bulk_build import rattler_bulk_build


@click.group()
def conda_recipe_manager() -> None:
    """
    Command line interface for conda recipe management commands.
    """
    pass


conda_recipe_manager.add_command(convert)
conda_recipe_manager.add_command(dep_scanner)
conda_recipe_manager.add_command(graph)
conda_recipe_manager.add_command(rattler_bulk_build)


if __name__ == "__main__":
    conda_recipe_manager()
