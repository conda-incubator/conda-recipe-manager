"""
:Description: Provides public types, type aliases, constants, and small classes used by the graphing module.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum, StrEnum, auto
from typing import no_type_check


class GraphType(StrEnum):
    """
    Categories of graph that the graphing module can work with
    """

    BUILD = "build"
    TEST = "test"


class GraphDirection(Enum):
    """
    Indicates which direction to traverse dependency information.
    """

    # The target package _depends on_ these other packages.
    DEPENDS_ON = auto()
    # The target package is _needed by_ these other packages.
    NEEDED_BY = auto()


class PackageStatsEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder for the `PackageStats` dataclass.
    Based on: https://stackoverflow.com/questions/51286748/make-the-python-json-encoder-support-pythons-new-dataclasses
    """

    @no_type_check
    def default(self, o: object) -> object:
        """
        Encoding instructions for the structure.

        :param o: Object to recursively encode.
        """
        if is_dataclass(o):
            return asdict(o)
        if isinstance(o, set):
            # Guarantees order for unit testing.
            l = list(o)
            l.sort()
            return l
        return super().default(o)


@dataclass
class PackageStats:
    """
    Convenience data structure that collects and stores various package-related statistics. These values are collected
    over the course of constructing a RecipeGraph instance.
    """

    # List of packages that have duplicate names
    package_name_duplicates: set[str] = field(default_factory=set)
    # List of recipes that failed to parse package names
    recipes_failed_to_parse: set[str] = field(default_factory=set)
    # Tracks packages that failed to parse recipes
    recipes_failed_to_parse_dependencies: dict[str, list[str]] = field(default_factory=dict)
    # Total number of successfully parsed recipes
    total_parsed_recipes: int = 0
    # Total number of recipes found
    total_recipes: int = 0
    # Total number of packages found
    total_packages: int = 0
