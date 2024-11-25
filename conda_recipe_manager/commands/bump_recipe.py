"""
:Description: CLI for bumping build number in recipe files.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Final, Optional, cast

import click

from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.fetcher.artifact_fetcher import from_recipe as af_from_recipe
from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher
from conda_recipe_manager.fetcher.http_artifact_fetcher import HttpArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import JsonPatchType

log = logging.getLogger(__name__)

## Constants ##


class RecipePaths:
    """
    Namespace to store common recipe path constants.
    """

    BUILD_NUM: Final[str] = "/build/number"
    SOURCE: Final[str] = "/source"
    SINGLE_SHA_256: Final[str] = f"{SOURCE}/sha256"
    VERSION: Final[str] = "/package/version"


# Common variable names used for source artifact hashes.
_COMMON_HASH_VAR_NAMES: Final[set[str]] = {"sha256", "hash", "hash_val", "hash_value"}

## Functions ##


def _validate_target_version(ctx: click.Context, param: str, value: str) -> str:  # pylint: disable=unused-argument
    """
    Provides additional input validation on the target package version.

    :param ctx: Click's context object
    :param param: Argument parameter name
    :param value: Target value to validate
    :raises click.BadParameter: In the event the input is not valid.
    :returns: The value of the argument, if valid.
    """
    # NOTE: `None` indicates the flag is not provided.
    if value == "":
        raise click.BadParameter("The target version cannot be an empty string.")
    return value


def _exit_on_failed_patch(recipe_parser: RecipeParser, patch_blob: JsonPatchType) -> None:
    """
    Convenience function that exits the program when a patch operation fails. This standardizes how we handle patch
    failures across all patch operations performed in this program.

    :param recipe_parser: Recipe file to update.
    :param patch_blob: Recipe patch to execute.
    """
    if recipe_parser.patch(patch_blob):
        log.debug("Executed patch: %s", patch_blob)
        return

    log.error("Couldn't perform the patch: %s", patch_blob)
    sys.exit(ExitCode.PATCH_ERROR)


def _pre_process_cleanup(recipe_content: str) -> str:
    """
    Performs some recipe clean-up tasks before parsing the recipe file. This should correct common issues and improve
    parsing compatibility.

    :param recipe_content: Recipe file content to fix.
    :returns: Post-processed recipe file text.
    """
    # TODO delete unused variables? Unsure if that may be too prescriptive.
    return RecipeParser.pre_process_remove_hash_type(recipe_content)


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
        log.error("`/build` key could not be found in the recipe.")
        sys.exit(ExitCode.ILLEGAL_OPERATION)

    # From the previous check, we know that `/build` exists. If `/build/number` is missing, it'll be added by
    # a patch-add operation and set to a default value of 0. Otherwise, we attempt to increment the build number, if
    # requested.
    if increment_build_num and recipe_parser.contains_value(RecipePaths.BUILD_NUM):
        build_number = recipe_parser.get_value(RecipePaths.BUILD_NUM)

        if not isinstance(build_number, int):
            log.error("Build number is not an integer.")
            sys.exit(ExitCode.ILLEGAL_OPERATION)

        _exit_on_failed_patch(
            recipe_parser,
            cast(JsonPatchType, {"op": "replace", "path": RecipePaths.BUILD_NUM, "value": build_number + 1}),
        )
        return

    _exit_on_failed_patch(recipe_parser, cast(JsonPatchType, {"op": "add", "path": RecipePaths.BUILD_NUM, "value": 0}))


def _update_version(recipe_parser: RecipeParser, target_version: str) -> None:
    """
    Attempts to update the `/package/version` field and/or the commonly used `version` JINJA variable.

    :param recipe_parser: Recipe file to update.
    :param target_version: Target version to update to.
    """
    # TODO Add V0 multi-output version support for some recipes (version field is duplicated in cctools-ld64 but not in
    # most multi-output recipes)

    # If the `version` variable is found, patch that. This is an artifact/pattern from Grayskull.
    old_variable = recipe_parser.get_variable("version", None)
    if old_variable is not None:
        recipe_parser.set_variable("version", target_version)
        # Generate a warning if `version` is not being used in the `/package/version` field. NOTE: This is a linear
        # search on a small list.
        if RecipePaths.VERSION not in recipe_parser.get_variable_references("version"):
            log.warning("`/package/version` does not use the defined JINJA variable `version`.")
        return

    op: Final[str] = "replace" if recipe_parser.contains_value(RecipePaths.VERSION) else "add"
    _exit_on_failed_patch(recipe_parser, {"op": op, "path": RecipePaths.VERSION, "value": target_version})


def _get_sha256(fetcher: HttpArtifactFetcher) -> str:
    """
    Wrapping function that attempts to retrieve an HTTP/HTTPS artifact with a retry mechanism.

    :param fetcher: Artifact fetching instance to use.
    :raises FetchError: If an issue occurred while downloading or extracting the archive.
    :returns: The SHA-256 hash of the artifact, if it was able to be downloaded.
    """
    # TODO retry mechanism, and log attempts
    # TODO attempt fetch in the background, especially if multiple fetch() calls are required.
    fetcher.fetch()
    return fetcher.get_archive_sha256()


def _update_sha256(recipe_parser: RecipeParser) -> None:
    """
    Attempts to update the SHA-256 hash(s) in the `/source` section of a recipe file, if applicable. Note that this is
    only required for build artifacts that are hosted as compressed software archives. If this field must be updated,
    a lengthy network request may be required to calculate the new hash.

    NOTE: For this to make any meaningful changes, the `version` field will need to be updated first.

    :param recipe_parser: Recipe file to update.
    """
    fetcher_tbl = af_from_recipe(recipe_parser, True)
    if not fetcher_tbl:
        log.warning("`/source` is missing or does not contain a supported source type.")
        return

    # Check to see if the SHA-256 hash might be set in a variable. In extremely rare cases, we log warnings to indicate
    # that the "correct" action is unclear and likely requires human intervention. Otherwise, if we see a hash variable
    # and it is used by a single source, we will edit the variable directly.
    hash_vars_set: Final[set[str]] = _COMMON_HASH_VAR_NAMES & set(recipe_parser.list_variables())

    if len(hash_vars_set) == 1 and len(fetcher_tbl) == 1:
        hash_var: Final[str] = next(iter(hash_vars_set))
        src_fetcher: Final[Optional[BaseArtifactFetcher]] = fetcher_tbl.get(RecipePaths.SOURCE, None)
        # By far, this is the most commonly seen case when a hash variable name is used.
        if (
            src_fetcher
            and isinstance(src_fetcher, HttpArtifactFetcher)
            # NOTE: This is a linear search on a small list.
            and RecipePaths.SINGLE_SHA_256 in recipe_parser.get_variable_references(hash_var)
        ):
            recipe_parser.set_variable(hash_var, _get_sha256(src_fetcher))
            return

        log.warning(
            (
                "Commonly used hash variable detected: `%s` but is not referenced by `/source/sha256`."
                " The hash value will be changed directly at `/source/sha256`."
            ),
            hash_var,
        )
    elif len(hash_vars_set) > 1:
        log.warning(
            "Multiple commonly used hash variables detected. Hash values will be changed directly in `/source` keys."
        )

    # NOTE: Each source _might_ have a different SHA-256 hash. This is the case for the `cctools-ld64` feedstock. That
    # project has a different implementation per architecture. However, in other circumstances, mirrored sources with
    # different hashes might imply there is a security threat. We will log some statistics so the user can best decide
    # what to do.
    unique_hashes: set[str] = set()
    total_hash_cntr = 0
    for src_path, fetcher in fetcher_tbl.items():
        if not isinstance(fetcher, HttpArtifactFetcher):
            continue

        sha = _get_sha256(fetcher)
        total_hash_cntr += 1
        unique_hashes.add(sha)
        sha_path = RecipeParser.append_to_path(src_path, "/sha256")

        # Guard against the unlikely scenario that the `sha256` field is missing.
        patch_op = "replace" if recipe_parser.contains_value(sha_path) else "add"
        _exit_on_failed_patch(recipe_parser, {"op": patch_op, "path": sha_path, "value": sha})

    log.info(
        "Found %d unique SHA-256 hash(es) out of a total of %d hash(es) in %d sources.",
        len(unique_hashes),
        total_hash_cntr,
        len(fetcher_tbl),
    )


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
    callback=_validate_target_version,
    help="New project version to target. Required if `--build-num` is NOT specified.",
)
def bump_recipe(recipe_file_path: str, build_num: bool, target_version: Optional[str]) -> None:
    """
    Bumps a recipe to a new version.

    RECIPE_FILE_PATH: Path to the target recipe file
    """

    if not build_num and target_version is None:
        log.error("The `--target-version` option must be set if `--build-num` is not specified.")
        sys.exit(ExitCode.CLICK_USAGE)

    try:
        recipe_content = Path(recipe_file_path).read_text(encoding="utf-8")
    except IOError:
        log.error("Couldn't read the given recipe file: %s", recipe_file_path)
        sys.exit(ExitCode.IO_ERROR)

    # Attempt to remove problematic recipe patterns that cause issues for the parser.
    recipe_content = _pre_process_cleanup(recipe_content)

    try:
        recipe_parser = RecipeParser(recipe_content)
    except Exception:  # pylint: disable=broad-except
        log.error("An error occurred while parsing the recipe file contents.")
        sys.exit(ExitCode.PARSE_EXCEPTION)

    # Attempt to update fields
    _update_build_num(recipe_parser, build_num)

    # NOTE: We check if `target_version` is specified to perform a "full bump" for type checking reasons. Also note that
    # the `build_num` flag is invalidated if we are bumping to a new version. The build number must be reset to 0 in
    # this case.
    if target_version is not None:
        if target_version == recipe_parser.get_value(RecipePaths.VERSION, default=None, sub_vars=True):
            log.warning("The provided target version is the same value found in the recipe file: %s", target_version)

        # Version must be updated before hash to ensure the correct artifact is hashed.
        _update_version(recipe_parser, target_version)
        _update_sha256(recipe_parser)

    Path(recipe_file_path).write_text(recipe_parser.render(), encoding="utf-8")
    sys.exit(ExitCode.SUCCESS)
