"""
File:           _selector_info.py
Description:    Provides the `SelectorInfo` class, used to store selector information.
"""
from __future__ import annotations

from typing import NamedTuple

from percy.parser._node import Node
from percy.parser._types import StrStack
from percy.parser._utils import stack_path_to_str


class SelectorInfo(NamedTuple):
    """
    Immutable structure that tracks information about how a particular selector is used.
    """

    node: Node
    path: StrStack

    def __str__(self) -> str:
        """
        Generates the string form of a `SelectorInfo` object. Useful for debugging.
        :returns: String representation of a `SelectorInfo` instance
        """
        path_str = stack_path_to_str(self.path.copy())
        return f"{self.node.short_str()} -> {path_str}"
