"""
:Description: Provides public types, type aliases, constants, and small classes used by the graphing module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class GraphType(Enum):
    """
    Categories of graph that the graphing module can work with
    """

    BUILD = auto()
    TEST = auto()


@dataclass
class PackageStats:
    """
    Convenience data structure that collects and stores various package-related statistics. These values are collected
    over the course of constructing a RecipeGraph instance.
    """

    # List of packages that have duplicate names
    package_name_duplicates: set[str] = field(default_factory=set)
    # List of SHA-256 hashes of recipes containing packages without package names
    recipes_of_unknown_packages: set[str] = field(default_factory=set)
    # List of recipes that failed to parse package names
    recipes_failed_to_parse: set[str] = field(default_factory=set)
    # Tracks packages that failed to parse recipes
    recipes_failed_to_parse_dependencies: set[str] = field(default_factory=set)
    # Total number of successfully parsed recipes
    total_parsed_recipes: int = 0
    # Total number of recipes found
    total_recipes: int = 0
    # Total number of packages found
    total_packages: int = 0
