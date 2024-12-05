"""
:Description: CLI for bumping build number in recipe files.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import sys
import time
from pathlib import Path
from typing import Final, Optional, cast

import click

from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.fetcher.artifact_fetcher import from_recipe as af_from_recipe
from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher
from conda_recipe_manager.fetcher.exceptions import FetchError
from conda_recipe_manager.fetcher.http_artifact_fetcher import HttpArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import JsonPatchType

# Truncates the `__name__` to the crm command name.
log = logging.getLogger(__name__.rsplit(".", maxsplit=1)[-1])

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

# Maximum number of retries to attempt when trying to fetch an external artifact.
_RETRY_LIMIT: Final[int] = 5
# How much longer (in seconds) we should wait per retry.
_DEFAULT_RETRY_INTERVAL: Final[int] = 30


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


def _validate_retry_interval(ctx: click.Context, param: str, value: float) -> float:  # pylint: disable=unused-argument
    """
    Provides additional input validation on the retry interval

    :param ctx: Click's context object
    :param param: Argument parameter name
    :param value: Target value to validate
    :raises click.BadParameter: In the event the input is not valid.
    :returns: The value of the argument, if valid.
    """
    if value <= 0:
        raise click.BadParameter("The retry interval must be a positive, non-zero floating-point value.")
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


def _exit_on_failed_fetch(fetcher: BaseArtifactFetcher) -> None:
    """
    Exits the script upon a failed fetch.

    :param fetcher: ArtifactFetcher instance used in the fetch attempt.
    """
    log.error("Failed to fetch `%s` after %s retries.", fetcher, _RETRY_LIMIT)
    sys.exit(ExitCode.HTTP_ERROR)


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


def _get_sha256(fetcher: HttpArtifactFetcher, retry_interval: float) -> str:
    """
    Wrapping function that attempts to retrieve an HTTP/HTTPS artifact with a retry mechanism.

    :param fetcher: Artifact fetching instance to use.
    :param retry_interval: Scalable interval between fetch requests.
    :raises FetchError: If an issue occurred while downloading or extracting the archive.
    :returns: The SHA-256 hash of the artifact, if it was able to be downloaded.
    """
    # NOTE: This is the most I/O-bound operation in `bump-recipe` by a country mile. At the time of writing,
    # running this operation in the background will not make any significant improvements to performance. Every other
    # operation is so fast in comparison, any gains would likely be lost with the additional overhead. This op is
    # also inherently reliant on having the version change performed ahead of time. In addition, parallelizing the
    # retries defeats the point of having a back-off timer.
    for retry_id in range(1, _RETRY_LIMIT + 1):
        try:
            log.info("Fetching artifact `%s`, attempt #%d", fetcher, retry_id)
            fetcher.fetch()
            return fetcher.get_archive_sha256()
        except FetchError:
            time.sleep(retry_id * retry_interval)
    raise FetchError(f"Failed to fetch `{fetcher}` after {_RETRY_LIMIT} retries.")


def _update_sha256_check_hash_var(
    recipe_parser: RecipeParser, retry_interval: float, fetcher_tbl: dict[str, BaseArtifactFetcher]
) -> bool:
    """
    Helper function that checks if the SHA-256 is stored in a variable. If it does, it performs the update.

    :param recipe_parser: Recipe file to update.
    :param retry_interval: Scalable interval between fetch requests.
    :param fetcher_tbl: Table of artifact source locations to corresponding ArtifactFetcher instances.
    :returns: True if `_update_sha256()` should return early. False otherwise.
    """
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
            try:
                recipe_parser.set_variable(hash_var, _get_sha256(src_fetcher, retry_interval))
            except FetchError:
                _exit_on_failed_fetch(src_fetcher)
            return True

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

    return False


def _update_sha256_fetch_one(src_path: str, fetcher: HttpArtifactFetcher, retry_interval: float) -> tuple[str, str]:
    """
    Helper function that retrieves a single HTTP source artifact, so that we can parallelize network requests.

    :param src_path: Recipe key path to the applicable artifact source.
    :param fetcher: Artifact fetching instance to use.
    :param retry_interval: Scalable interval between fetch requests.
    :raises FetchError: In the event that the retry mechanism failed to fetch a source artifact.
    :returns: A tuple containing the path to and the actual SHA-256 value to be updated.
    """
    sha = _get_sha256(fetcher, retry_interval)
    return (RecipeParser.append_to_path(src_path, "/sha256"), sha)


def _update_sha256(recipe_parser: RecipeParser, retry_interval: float) -> None:
    """
    Attempts to update the SHA-256 hash(s) in the `/source` section of a recipe file, if applicable. Note that this is
    only required for build artifacts that are hosted as compressed software archives. If this field must be updated,
    a lengthy network request may be required to calculate the new hash.

    NOTE: For this to make any meaningful changes, the `version` field will need to be updated first.

    :param recipe_parser: Recipe file to update.
    :param retry_interval: Scalable interval between fetch requests.
    """
    fetcher_tbl = af_from_recipe(recipe_parser, True)
    if not fetcher_tbl:
        log.warning("`/source` is missing or does not contain a supported source type.")
        return

    if _update_sha256_check_hash_var(recipe_parser, retry_interval, fetcher_tbl):
        return

    # NOTE: Each source _might_ have a different SHA-256 hash. This is the case for the `cctools-ld64` feedstock. That
    # project has a different implementation per architecture. However, in other circumstances, mirrored sources with
    # different hashes might imply there is a security threat. We will log some statistics so the user can best decide
    # what to do.
    unique_hashes: set[str] = set()

    # Filter-out artifacts that don't need a SHA-256 hash.
    http_fetcher_tbl: Final[dict[str, HttpArtifactFetcher]] = {
        k: v for k, v in fetcher_tbl.items() if isinstance(v, HttpArtifactFetcher)
    }
    # Parallelize on acquiring multiple source artifacts on the network. In testing, using a process pool took
    # significantly more time and resources. That aligns with how I/O bound this process is. We use the
    # `ThreadPoolExecutor` class over a `ThreadPool` so the script may exit gracefully if we failed to acquire an
    # artifact.
    sha_path_to_sha_tbl: dict[str, str] = {}
    with cf.ThreadPoolExecutor() as executor:
        artifact_futures_tbl = {
            executor.submit(_update_sha256_fetch_one, src_path, fetcher, retry_interval): fetcher
            for src_path, fetcher in http_fetcher_tbl.items()
        }
        for future in cf.as_completed(artifact_futures_tbl):
            fetcher = artifact_futures_tbl[future]
            try:
                resolved_tuple = future.result()
                sha_path_to_sha_tbl[resolved_tuple[0]] = resolved_tuple[1]
            except FetchError:
                _exit_on_failed_fetch(fetcher)

    for sha_path, sha in sha_path_to_sha_tbl.items():
        unique_hashes.add(sha)
        # Guard against the unlikely scenario that the `sha256` field is missing.
        patch_op = "replace" if recipe_parser.contains_value(sha_path) else "add"
        _exit_on_failed_patch(recipe_parser, {"op": patch_op, "path": sha_path, "value": sha})

    log.info(
        "Found %d unique SHA-256 hash(es) out of a total of %d hash(es) in %d sources.",
        len(unique_hashes),
        len(sha_path_to_sha_tbl),
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
    "-d",
    "--dry-run",
    is_flag=True,
    help="Performs a dry-run operation that prints the recipe to STDOUT and does not save to the recipe file.",
)
@click.option(
    "-t",
    "--target-version",
    default=None,
    type=str,
    callback=_validate_target_version,
    help="New project version to target. Required if `--build-num` is NOT specified.",
)
@click.option(
    "-i",
    "--retry-interval",
    default=_DEFAULT_RETRY_INTERVAL,
    type=float,
    callback=_validate_retry_interval,
    help=(
        "Retry interval (in seconds) for network requests. Scales with number of failed attempts."
        f" Defaults to {_DEFAULT_RETRY_INTERVAL} seconds"
    ),
)
def bump_recipe(
    recipe_file_path: str, build_num: bool, dry_run: bool, target_version: Optional[str], retry_interval: float
) -> None:
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
        _update_sha256(recipe_parser, retry_interval)

    if dry_run:
        print(recipe_parser.render())
    else:
        Path(recipe_file_path).write_text(recipe_parser.render(), encoding="utf-8")
    sys.exit(ExitCode.SUCCESS)
