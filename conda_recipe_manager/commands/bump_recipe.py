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
from conda_recipe_manager.parser.recipe_reader import RecipeReader
from conda_recipe_manager.types import JsonPatchType


def _exit_on_failed_patch(recipe_parser: RecipeParser, patch_blob: JsonPatchType) -> None:
    """
    Convenience function that exits the program when a patch operation fails. This standardizes how we handle patch
    failures across all patch operations performed in this program.

    :param recipe_parser: Recipe file to update.
    :param patch_blob: Recipe patch to execute.
    """
    if recipe_parser.patch(patch_blob):
        return

    print_err(f"Couldn't perform the patch: {patch_blob}.")
    sys.exit(ExitCode.PATCH_ERROR)


def _update_build_num(recipe_parser: RecipeParser, increment_build_num: bool) -> None:
    """
    Attempts to update the build number in a recipe file.

    :param recipe_parser: Recipe file to update.
    :param increment_build_num: Increments the `/build/number` field by 1 if set to `True`. Otherwise resets to 0.
    """

    # Try to get "build" key from the recipe, exit if not found
    try:
        recipe_parser.get_value("/build")
    except KeyError:
        print_err("`/build` key could not be found in the recipe.")
        sys.exit(ExitCode.ILLEGAL_OPERATION)

    # If build key is found, try to get build/number key in case of `build_num` set to false, `build/number` key will be
    # added and set to zero when `build_num` is set to true, throw error and sys.exit()

    # TODO use contains_value() instead of try catch
    try:
        build_number = recipe_parser.get_value("/build/number")
        if increment_build_num:
            if not isinstance(build_number, int):
                print_err("Build number is not an integer.")
                sys.exit(ExitCode.ILLEGAL_OPERATION)

            _exit_on_failed_patch(
                recipe_parser,
                cast(JsonPatchType, {"op": "replace", "path": "/build/number", "value": build_number + 1}),
            )
            return
    except KeyError:
        if increment_build_num:
            print_err("`/build/number` key could not be found in the recipe.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)

    _exit_on_failed_patch(recipe_parser, cast(JsonPatchType, {"op": "add", "path": "/build/number", "value": 0}))


def _update_sha256(recipe_parser: RecipeParser) -> None:
    """
    Attempts to update the SHA-256 hash(s) in the `/source` section of a recipe file, if applicable. Note that this is
    only required for build artifacts that are hosted as compressed software archives. If this field must be updated,
    a lengthy network request may be required to calculate the new hash.

    NOTE: For this to make any meaningful changes, the `version` field will need to be updated first.

    :param recipe_parser: Recipe file to update.
    """
    fetcher_lst = af_from_recipe(recipe_parser, True)
    if not fetcher_lst:
        # TODO log
        return

    # TODO handle case where SHA is stored in one or more variables (see cctools-ld64.yaml)
    # TODO handle case where SHA is a variable

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
        sha_path = RecipeReader.append_to_path(src_path, "/sha256")

        # Guard against the unlikely scenario that the `sha256` field is missing.
        patch_op = "replace" if recipe_parser.contains_value(sha_path) else "add"
        _exit_on_failed_patch(recipe_parser, {"op": patch_op, "path": sha_path, "value": sha})


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

    # Attempt to update fields
    _update_build_num(recipe_parser, build_num)
    if not build_num:
        _update_sha256(recipe_parser)

    Path(recipe_file_path).write_text(recipe_parser.render(), encoding="utf-8")
    sys.exit(ExitCode.SUCCESS)
