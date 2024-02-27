"""
File:           enums.py
Description:    Provides enumerated types used by the parser.
"""
from __future__ import annotations

from enum import Enum


class SelectorConflictMode(Enum):
    """
    Defines how to handle the addition of a selector if one already exists.
    """

    AND = 1  # Logically "and" the new selector with the old
    OR = 2  # Logically "or" the new selector with the old
    REPLACE = 3  # Replace the existing selector
