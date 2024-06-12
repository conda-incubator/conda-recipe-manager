"""
File:           conda_recipe_manager.py
Description:    Base CLI for all `conda-recipe-manager` commands
"""

from __future__ import annotations

import click

from conda_recipe_manager.commands.convert import convert
from conda_recipe_manager.commands.rattler_bulk_build import rattler_bulk_build
from conda_recipe_manager.commands.update_feedstock import update_feedstock


@click.group()
def conda_recipe_manager() -> None:
    """
    Command line interface for conda recipe management commands.
    """
    pass


conda_recipe_manager.add_command(convert)
conda_recipe_manager.add_command(rattler_bulk_build)
conda_recipe_manager.add_command(update_feedstock)


if __name__ == "__main__":
    conda_recipe_manager()
