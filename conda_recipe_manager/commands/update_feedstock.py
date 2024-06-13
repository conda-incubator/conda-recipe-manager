"""
File:           update_feedstock.py
Description:    Provides a command that automates the process of adding a V1 recipe file to an existing feedstock repo.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Final, Optional, cast

import click
from pygit2 import clone_repository  # type: ignore[import-untyped]

from conda_recipe_manager.commands.convert import convert_file
from conda_recipe_manager.commands.utils.print import print_err
from conda_recipe_manager.commands.utils.types import V0_FORMAT_RECIPE_FILE_NAME, V1_FORMAT_RECIPE_FILE_NAME, ExitCode


def _validate_remote(_0: click.Context, _1: str, value: Optional[str]) -> Optional[str]:
    """
    Validates the REMOTE option.
    :param value: Remote value to validate
    :raises: BadParameter if the value could not be validated
    :returns: Validated value
    """
    if value is None:
        return None

    if (
        not value.endswith(".git")
        # TODO: Add support for SSH protocol
        and not value.startswith("https://github.com/")
    ):
        raise click.BadParameter("Remote location provided is not a recognized GitHub repo.")
    return value


def _validate_path(ctx: click.Context, _: str, value: Path) -> Path:
    """
    Validates the PATH argument.
    :param ctx: Click context
    :param value: Path value to validate
    :raises: BadParameter if the value could not be validated
    :returns: Validated value
    """
    # If we are pulling from a remote location, we are allowed to create a new, non-existent path
    if "remote" in cast(dict[str, str], ctx.params):
        try:
            value.mkdir(parents=True, exist_ok=False)
        except FileExistsError as e:
            raise click.BadParameter("Path cannot contain an existing git repo.") from e
        except Exception as e:
            raise click.BadParameter("Path could not be created.") from e
        return value

    # If we are using an existing repo, the repo must exist.
    if not (value / ".git").exists():
        raise click.BadParameter("Could not find git repo in path provided.")

    return value


def _get_v0_files(path: Path) -> list[Path]:
    """
    Returns a list of V0 files found in a path.
    :param path: Path of the feedstock repo
    :returns: A list of all V0 recipe files found in the feedstock repo
    """
    files: list[Path] = []
    for file_path in path.rglob(V0_FORMAT_RECIPE_FILE_NAME):
        files.append(file_path)
    return files


@click.command(
    short_help="Streamlines adding a V1 recipe file to an existing feedstock repository.",
)
@click.option(
    "--remote",
    "-r",
    type=str,
    callback=_validate_remote,
    help="URI to a remote feedstock hosted on GitHub. HTTPS is currently supported.",
)
@click.argument(
    "path",
    type=click.Path(path_type=Path),  # type: ignore[misc]
    callback=_validate_path,
)
@click.pass_context
def update_feedstock(_: click.Context, path: Path, remote: Optional[str]) -> None:
    """
    Streamlines the process of adding a V1 recipe file to an existing feedstock repo. This creates a new V1 file based
    on an existing `meta.yaml` (V0) recipe file and validates the output. If validation succeeds, this script
    automatically opens a pull request against the feedstock repository.

    PATH is a path to a local feedstock repository. If the `--remote` option is used, this is the directory that the
    remote repository will be cloned into.
    """
    start_time: Final[float] = time.time()

    # If `--remote` is specified, clone to `path`
    if remote is not None:
        print(f"Cloning {remote}...")
        clone_repository(remote, path)

    # Validate repo has at least 1 meta.yaml
    v0_files: Final[list[Path]] = _get_v0_files(path)
    if not v0_files:
        print_err(f"No `{V0_FORMAT_RECIPE_FILE_NAME}` recipe files found in `{path}`")
        sys.exit(ExitCode.NO_FILES_FOUND)

    for v0_file in v0_files:
        v1_file = v0_file.parent / V1_FORMAT_RECIPE_FILE_NAME

        print(f"Converting {v0_file}...")
        conversion_result = convert_file(v0_file, v1_file, False, False)
        if not conversion_result.code in {ExitCode.SUCCESS, ExitCode.RENDER_WARNINGS}:
            sys.exit(conversion_result.code)

        print(f"Testing {v1_file}...")
        # TODO add dry-run test

    exec_time: Final[float] = round(time.time() - start_time, 2)
    print(f"Total time: {exec_time}")

    sys.exit(ExitCode.SUCCESS)
