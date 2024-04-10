"""
File:           print.py
Description:    Provides print utility functions
"""

from __future__ import annotations

import sys
from typing import Final

from conda_recipe_manager.parser.types import MessageCategory, MessageTable


def print_out(*args, **kwargs) -> None:  # type: ignore
    """
    Convenience wrapper that prints to STDOUT
    """
    print(*args, file=sys.stdout, **kwargs)  # type: ignore


def print_err(*args, **kwargs) -> None:  # type: ignore
    """
    Convenience wrapper that prints to STDERR
    """
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
