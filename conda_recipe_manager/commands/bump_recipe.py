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


@click.command(short_help="Bump recipe build version.")
@click.argument("recipe_file_path", type=click.Path(exists=True, path_type=str))
@click.option(
    "--build-num",
    is_flag=True,
    help="Bump the build number by 1.",
)
def bump_recipe(recipe_file_path: str, build_num: bool) -> None:
    """
    Bump recipe version.

    RECIPE_FILE_PATH: Path to the target recipe file
    """
    try:
        contents_recipe = Path(recipe_file_path).read_text(encoding="utf-8")
    except IOError:
        print_err(f"Couldn't read the given recipe file: {recipe_file_path}")
        sys.exit(ExitCode.IO_ERROR)  # untested

    try:
        recipe_parser = RecipeParser(contents_recipe)
        error_code = ExitCode.SUCCESS
    except Exception:  # pylint: disable=broad-except
        print_err("An error occurred while parsing the recipe file contents.")
        sys.exit(ExitCode.PARSE_EXCEPTION)  # untested

    if build_num:
        error_code = ExitCode.SUCCESS
        try:
            build_number = recipe_parser.get_value("/build/number")
        except KeyError:
            print_err("`/build/number` key could not be found in the recipe.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)

        if not isinstance(build_number, int):
            print_err("Build number is not an integer.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)
        required_patch_blob = cast(JsonPatchType, {"op": "replace", "path": "/build/number", "value": build_number + 1})
        recipe_parser.patch(required_patch_blob)
        Path(recipe_file_path).write_text(recipe_parser.render(), encoding="utf-8")
        sys.exit(error_code)
