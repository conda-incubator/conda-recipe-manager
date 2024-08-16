"""
:Description: Provides enumerated types used by the parser.
"""

from __future__ import annotations

from enum import Enum, IntEnum, StrEnum
from typing import Final


class SchemaVersion(IntEnum):
    """
    Recipe `schema_version` enumeration. The Pre-CEP-13 "schema" is designated as "Version 0" and does not require
    a `schema_version` field in the recipe file.
    """

    V0 = 0  # Pre-CEP-13, effectively defined by conda-build
    V1 = 1  # CEP-13+


class SelectorConflictMode(Enum):
    """
    Defines how to handle the addition of a selector if one already exists.
    """

    AND = 1  # Logically "and" the new selector with the old
    OR = 2  # Logically "or" the new selector with the old
    REPLACE = 3  # Replace the existing selector


class LogicOp(StrEnum):
    """
    Logic operators used in selector syntax
    """

    AND = "and"
    OR = "or"
    NOT = "not"


# Set of all Logic operators
ALL_LOGIC_OPS: Final[set[LogicOp]] = set(LogicOp)
