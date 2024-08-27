"""
:Description: CLI for patching JSON blobs to recipe files.
"""

from __future__ import annotations

import click


@click.command(short_help="Add JSON blobs to recipe files.")
def patch() -> None:
    """
    Add JSON blobs to recipe files.
    """
