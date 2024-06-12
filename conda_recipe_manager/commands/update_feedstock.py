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

SUCCESS: Final[int] = 0


def validate_remote(_0: click.Context, _1: str, value: str) -> str:
    """
    Validates the REMOTE option.
    :param value: Remote value to validate
    """
    if (
        not value.endswith(".git")
        or not value.startswith("git@github.com:")
        or not value.startswith("https://github.com/")
    ):
        raise click.BadParameter("Remote location provided is not a recognized GitHub repo.")
    return value


def validate_path(ctx: click.Context, _: str, value: Path) -> Path:
    """
    Validates the PATH argument.
    :param ctx: Click context
    :param value: Path value to validate
    """
    # If we are pulling from a remote location, we are allowed to create a path
    if "remote" in cast(dict[str, str], ctx.params):
        try:
            value.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise click.BadParameter("Path could not be created.") from e
        return value

    # If we are using an existing repo, the repo must exist.
    if (value / ".git").exists():
        raise click.BadParameter("Could not find git repo in path provided.")

    return value


@click.command(
    short_help="Streamlines adding a V1 recipe file to an existing feedstock repository.",
)
@click.option(
    "--remote",
    "-r",
    type=str,
    callback=validate_remote,
    help="URI to a remote feedstock hosted on GitHub. HTTPS and SSH are supported.",
)
@click.argument(
    "path",
    type=click.Path(path_type=Path),  # type: ignore[misc]
    callback=validate_path,
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
        clone_repository(remote, path)

    # TODO
    # Determine the name of the feedstock.
    # feedstock_name: Final[str] = ""

    exec_time: Final[float] = time.time() - start_time
    print(f"Total time: {exec_time}")

    sys.exit(SUCCESS)
