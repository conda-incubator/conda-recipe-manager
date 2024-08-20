"""
:Description: Provides public types, type aliases, constants, and small classes used by the graphing module.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum


class GraphType(StrEnum):
    """
    Categories of graph that the graphing module can work with
    """

    BUILD = "build"
    TEST = "test"


class PackageStatsEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder for the `PackageStats` dataclass.
    Based on: https://stackoverflow.com/questions/51286748/make-the-python-json-encoder-support-pythons-new-dataclasses
    """

    def default(self, obj: object) -> object:
        """
        Encoding instructions for the structure.

        :param obj: Object to recursively encode.
        """
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


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
