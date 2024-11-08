"""
:Description: CLI for bumping build number in recipe files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import click

from conda_recipe_manager.commands.utils.print import print_err
from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import JsonPatchType


# TODO Improve. In order for `click` to play nice with `pyfakefs`, we set `path_type=str` and delay converting to a
# `Path` instance. This is caused by how `click` uses decorators. See these links for more detail:
# - https://pytest-pyfakefs.readthedocs.io/en/latest/troubleshooting.html#pathlib-path-objects-created-outside-of-tests
# - https://github.com/pytest-dev/pyfakefs/discussions/605
@click.command(short_help="Bumps a recipe file to a new version.")
@click.argument("recipe_file_path", type=click.Path(exists=True, path_type=str))
@click.option(
    "--build-num",
    is_flag=True,
    help="Bump the build number by 1.",
)
def bump_recipe(recipe_file_path: str, build_num: bool) -> None:
    """
    Bumps a recipe to a new version.

    RECIPE_FILE_PATH: Path to the target recipe file
    """
    try:
        contents_recipe = Path(recipe_file_path).read_text(encoding="utf-8")
    except IOError:
        print_err(f"Couldn't read the given recipe file: {recipe_file_path}")
        sys.exit(ExitCode.IO_ERROR)

    try:
        recipe_parser = RecipeParser(contents_recipe)
    except Exception:  # pylint: disable=broad-except
        print_err("An error occurred while parsing the recipe file contents.")
        sys.exit(ExitCode.PARSE_EXCEPTION)

    if build_num:
        try:
            build_number = recipe_parser.get_value("/build/number")
        except KeyError:
            print_err("`/build/number` key could not be found in the recipe.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)

        if not isinstance(build_number, int):
            print_err("Build number is not an integer.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)

        required_patch_blob = cast(JsonPatchType, {"op": "replace", "path": "/build/number", "value": build_number + 1})

        if not recipe_parser.patch(required_patch_blob):
            print_err(f"Couldn't perform the patch: {required_patch_blob}.")
            sys.exit(ExitCode.PARSE_EXCEPTION)

        Path(recipe_file_path).write_text(recipe_parser.render(), encoding="utf-8")
        sys.exit(ExitCode.SUCCESS)
    print_err("Sorry, the default bump behaviour has not been implemented yet.")
