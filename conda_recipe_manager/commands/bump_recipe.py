"""
:Description: CLI for bumping build number in recipe files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final, Optional, cast

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

    # From the previous check, we know that `/build` exists. If `/build/number` is missing, it'll be added by
    # a patch-add operation and set to a default value of 0. Otherwise, we attempt to increment the build number, if
    # requested.
    if increment_build_num and recipe_parser.contains_value("/build/number"):
        build_number = recipe_parser.get_value("/build/number")

        if not isinstance(build_number, int):
            print_err("Build number is not an integer.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)

        _exit_on_failed_patch(
            recipe_parser,
            cast(JsonPatchType, {"op": "replace", "path": "/build/number", "value": build_number + 1}),
        )
        return

    _exit_on_failed_patch(recipe_parser, cast(JsonPatchType, {"op": "add", "path": "/build/number", "value": 0}))


def _update_version(recipe_parser: RecipeParser, target_version: str) -> None:  # pylint: disable=unused-argument
    """
    Attempts to update the `/package/version` field and/or the commonly used `version` JINJA variable.

    :param recipe_parser: Recipe file to update.
    :param target_version: Target version to update to.
    """
    # TODO Add V0 multi-output version support for some recipes (version field is duplicated in cctools-ld64 but not in
    # most multi-output recipes)
    # TODO branch on `/package/version` being specified without a `version` variable
    old_variable = recipe_parser.get_variable("version", None)
    if old_variable is not None:
        recipe_parser.set_variable("version", target_version)
        # TODO ensure that `version` is being used in `/package/version`
        # NOTE: This is a linear search on a small list.
        if "/package/version" not in recipe_parser.get_variable_references():
            # TODO log a warning; still patch?
            pass
        return

    # TODO handle missing `package` field
    op: Final[str] = "replace" if recipe_parser.contains_value("/package/version") else "add"
    recipe_parser.patch({"op": op, "path": "/package/version", "value": target_version})


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
    "-b",
    "--build-num",
    is_flag=True,
    help="Bump the build number by 1.",
)
@click.option(
    "-t",
    "--target-version",
    default=None,
    type=str,
    help="New project version to target. Required if `--build-num` is NOT specified.",
)
def bump_recipe(recipe_file_path: str, build_num: bool, target_version: Optional[str]) -> None:
    """
    Bumps a recipe to a new version.

    RECIPE_FILE_PATH: Path to the target recipe file
    """

    if not build_num and target_version is None:
        print_err("The `--target-version` option must be set if `--build-num` is not specified.")
        sys.exit(ExitCode.CLICK_USAGE)

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

    # NOTE: We check if `target_version` is specified to perform a "full bump" for type checking reasons. Also note that
    # the `build_num` flag is invalidated if we are bumping to a new version. The build number must be reset to 0 in
    # this case.
    if target_version is not None:
        # Version must be updated before hash to ensure the correct artifact is hashed.
        _update_version(recipe_parser, target_version)
        _update_sha256(recipe_parser)

    Path(recipe_file_path).write_text(recipe_parser.render(), encoding="utf-8")
    sys.exit(ExitCode.SUCCESS)
