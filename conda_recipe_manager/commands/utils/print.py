"""
:Description: Provides print utility functions
"""

from __future__ import annotations

import sys
from typing import Final

from conda_recipe_manager.types import MessageCategory, MessageTable


def print_out(*args, print_enabled: bool = True, **kwargs) -> None:  # type: ignore
    """
    Convenience wrapper that prints to STDOUT

    :param print_enabled: (Optional) Flag to enable printing. Enabled by default.
    """
    if print_enabled:
        print(*args, file=sys.stdout, **kwargs)  # type: ignore


def print_err(*args, print_enabled: bool = True, **kwargs) -> None:  # type: ignore
    """
    Convenience wrapper that prints to STDERR

    :param print_enable: (Optional) Flag to enable printing. Enabled by default.
    """
    if print_enabled:
        print(*args, file=sys.stderr, **kwargs)  # type: ignore


def print_messages(category: MessageCategory, msg_tbl: MessageTable) -> None:
    """
    Convenience function for dumping a series of messages of a certain category

    :param category: Category of messages to print
    :param msg_tbl: `MessageTable` instance containing the messages to print
    """
    msgs: Final[list[str]] = msg_tbl.get_messages(category)
    for msg in msgs:
        print_err(f"[{category.upper()}]: {msg}")
