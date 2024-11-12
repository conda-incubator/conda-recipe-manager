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
from conda_recipe_manager.fetcher.artifact_fetcher import from_recipe as af_from_recipe
from conda_recipe_manager.fetcher.http_artifact_fetcher import HttpArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import JsonPatchType


def _update_sha256(recipe_parser: RecipeParser) -> None:
    """
    Attempts to update the SHA-256 hash(s) in the `/source` section of a recipe file, if applicable. Note that this is
    only required for build artifacts that are hosted as compressed software archives. If this field must be updated,
    a lengthy network request may be required to calculate the new hash.

    :param recipe_parser: Recipe file to update.
    """
    fetcher_lst = af_from_recipe(recipe_parser, True)
    if not fetcher_lst:
        return

    # TODO handle case where SHA is stored in one or more variables (see cctools-ld64.yaml)

    # TODO Future: Figure out
    # NOTE: Each source _might_ have a different SHA-256 hash. This is the case for the `cctools-ld64` feedstock. That
    # project has a different implementation per architecture. However, in other circumstances, mirrored sources with
    # different hashes might imply there is a security threat.
    for src_path, fetcher in fetcher_lst.items():
        if not isinstance(fetcher, HttpArtifactFetcher):
            continue

        # TODO retry mechanism
        # TODO attempt fetch in the background, especially if multiple fetch() calls are required.
        fetcher.fetch()
        sha = fetcher.get_archive_sha256()
        # TODO make this an `add` op if the path is missing
        recipe_parser.patch({"op": "replace", "path": src_path, "value": sha})


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
