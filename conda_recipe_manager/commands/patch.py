"""
:Description: CLI for patching JSON blobs to recipe files.
"""

from __future__ import annotations

from pathlib import Path

import click


@click.argument("recipe file path", type=click.Path(exists=True, path_type=Path))  # type: ignore[misc]
@click.argument("json file path", type=click.Path(exists=True, path_type=Path))  # type: ignore[misc]
@click.command(short_help="Add JSON blobs to recipe files.")
def patch() -> None:
    """
    Add JSON blobs to recipe files.
    """
