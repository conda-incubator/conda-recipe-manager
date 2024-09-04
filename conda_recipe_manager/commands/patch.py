"""
:Description: CLI for patching JSON blobs to recipe files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import click

from conda_recipe_manager.commands.utils.print import print_err
from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.parser.exceptions import JsonPatchValidationException
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import JsonPatchType


def _pre_patch_validate(
    json_patch_file_path: Path, recipe_file_path: Path
) -> tuple[JsonPatchType | list[JsonPatchType], RecipeParser]:
    """
    Confirm that the json patch file and recipe file can be read and that the recipe parser object is created.
    """
    try:
        contents_json = cast(JsonPatchType | list[JsonPatchType], json.loads(json_patch_file_path.read_text()))
    except json.JSONDecodeError:
        print(f"Non-JSON file provided: {json_patch_file_path}")
        sys.exit(ExitCode.JSON_ERROR)

    try:
        contents_recipe = recipe_file_path.read_text()
    except IOError:
        print_err(f"Couldn't read the given recipe file: {recipe_file_path}")
        sys.exit(ExitCode.IO_ERROR)

    try:
        recipe_parser = RecipeParser(contents_recipe)
    except Exception:  # pylint: disable=broad-except
        print_err("An error occurred while parsing the recipe file contents.")
        sys.exit(ExitCode.PARSE_EXCEPTION)

    return contents_json, recipe_parser


@click.argument("recipe_file_path", type=click.Path(exists=True, path_type=Path))  # type: ignore[misc]
@click.argument("json_patch_file_path", type=click.Path(exists=True, path_type=Path))  # type: ignore[misc]
@click.command(short_help="Add JSON blobs to recipe files.")
def patch(json_patch_file_path: Path, recipe_file_path: Path) -> None:
    """
    Patch JSON blobs to recipe files.
    """
    contents_json, recipe_parser = _pre_patch_validate(json_patch_file_path, recipe_file_path)

    if not isinstance(contents_json, list):
        contents_json = cast(list[JsonPatchType], list(contents_json))

    error_code = ExitCode.SUCCESS
    try:
        for patch_blob in contents_json:
            if not recipe_parser.patch(patch_blob):
                error_code = ExitCode.ILLEGAL_OPERATION
                break
    except JsonPatchValidationException:
        print_err("The patch provided did not follow the expected schema.")
        error_code = ExitCode.JSON_ERROR

    recipe_file_path.write_text(recipe_parser.render())
    sys.exit(error_code)
