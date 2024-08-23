"""
:Description: Provides types and utilities for managing recipe dependencies.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import NamedTuple, Optional

from conda.models.match_spec import MatchSpec

from conda_recipe_manager.parser.selector_parser import SelectorParser
from conda_recipe_manager.parser.types import SchemaVersion


class DependencySection(Enum):
    """
    Enumerates dependency sections found in a recipe file.
    """

    BUILD = auto()
    HOST = auto()
    RUN = auto()
    RUN_CONSTRAINTS = auto()
    # NOTE: `run_exports` was not in the `requirements/` section in the V0 format
    RUN_EXPORTS = auto()
    # NOTE:
    #   - Test dependencies are not found under the `requirements/` section, they are found under the testing section.
    #   - There are major changes to the testing section in V1.
    # TODO TEST not covered in get_all_dependencies()
    TESTS = auto()


def dependency_section_to_str(section: DependencySection, schema: SchemaVersion) -> str:
    """
    Converts a dependency section enumeration to the equivalent string found in the recipe, based on the current
    schema.

    :param section: Target dependency section
    :param schema: Target recipe schema
    :returns: String equivalent of the recipe schema
    """
    # `match` is used here so the static analyzer can ensure all cases are covered
    match schema:
        case SchemaVersion.V0:
            match section:
                case DependencySection.BUILD:
                    return "build"
                case DependencySection.HOST:
                    return "host"
                case DependencySection.RUN:
                    return "run"
                case DependencySection.RUN_CONSTRAINTS:
                    return "run_constrained"
                case DependencySection.RUN_EXPORTS:
                    return "run_exports"
                case DependencySection.TESTS:
                    return "requires"
        case SchemaVersion.V1:
            match section:
                case DependencySection.BUILD:
                    return "build"
                case DependencySection.HOST:
                    return "host"
                case DependencySection.RUN:
                    return "run"
                case DependencySection.RUN_CONSTRAINTS:
                    return "run_constraints"
                case DependencySection.RUN_EXPORTS:
                    return "run_exports"
                case DependencySection.TESTS:
                    return "requires"


def str_to_dependency_section(s: str) -> Optional[DependencySection]:
    """
    Converts a dependency section string to a section enumeration.

    :param s: Target string to convert
    :returns: String equivalent of the recipe schema. None if the string is unrecognized.
    """
    # `match` is used here so the static analyzer can ensure all cases are covered
    match s.strip().lower():
        case "build":
            return DependencySection.BUILD
        case "host":
            return DependencySection.HOST
        case "run":
            return DependencySection.RUN
        case "run_constrained":  # V0
            return DependencySection.RUN_CONSTRAINTS
        case "run_constraints":  # V1
            return DependencySection.RUN_CONSTRAINTS
        case "run_exports":
            return DependencySection.RUN_EXPORTS
        case _:
            return None


class Dependency(NamedTuple):
    """
    Structure that contains metadata about a dependency found in the recipe. This is immutable by design.
    """

    # Owning package name
    required_by: str
    # Path in the recipe where this dependency was found
    path: str
    # Identifies what kind of dependency this is
    type: DependencySection
    # Parses the dependency's name and version constraints
    match_spec: MatchSpec
    # The selector applied to this dependency, if applicable
    selector: Optional[SelectorParser] = None


# Maps-out dependencies found in a recipe. Maps package name -> list of parsed dependencies.
DependencyMap = dict[str, list[Dependency]]
