"""
:Description: Provides types and utilities for managing recipe dependencies.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Final, NamedTuple, Optional, cast

from conda.models.match_spec import InvalidMatchSpec, MatchSpec

from conda_recipe_manager.parser._types import Regex
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


class DependencyConflictMode(Enum):
    """
    Mode of operation to use when handling duplicate dependencies (identified by name).
    """

    # Replace the existing dependency with the incoming dependency. Append to the end if there is no duplicate.
    REPLACE = auto()
    # Ignore the incoming dependency if there is a duplicate and do not modify any existing selector. Otherwise, append
    # to the end of the list.
    IGNORE = auto()
    # Include both dependencies, always appending to the end of the list.
    USE_BOTH = auto()
    # Write over what exists at the index provided, regardless of duplicates.
    EXACT_POSITION = auto()


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
        # This is included for the sake of completeness. Realistically, test dependencies should be detected by looking
        # at the testing section, not `/requirements`.
        case "requires":
            return DependencySection.TESTS
        case _:
            return None


class DependencyData:
    """
    Augments the dependency string found in a list of dependencies. This attempts to discern between dependencies that
    we can evaluate and render and dependencies that we cannot.
    """

    def __init__(self, raw_s: str, sub_s: Optional[str] = None):
        """
        Constructs a DependencyData instance.

        :param raw_s: "Raw"/original string from the recipe file to process.
        :param sub_s: (Optional) If provided, this is a string containing the variable-substituted version of the
            dependency string. For example, the line `python {{ python_min }}` would be passed-in (by the recipe parser)
            as `raw_str = "python {{ python_min }}"` and `sub_s = python 3.7`. Substitutions MUST be handled by a
            recipe parser!
        """
        self._raw_s: Final[str] = raw_s
        self._sub_s: Final[Optional[str]] = None if sub_s is None else sub_s

        # Helper function to perform a one-time initialization of `MatchSpec`, if possible.
        def _set_match_spec() -> Optional[MatchSpec]:
            # Use the variable-substituted string when possible. This should have greater compatibility with `MatchSpec`
            # than an unrendered string.
            s: Final[str] = raw_s if sub_s is None else sub_s
            if Regex.JINJA_V0_SUB.search(s) or Regex.JINJA_V1_SUB.search(s):
                return None
            try:
                return MatchSpec(s)
            except (ValueError, InvalidMatchSpec):
                # In an effort to be more resilient, fallback to a less powerful variant of this class.
                return None

        self._match_spec: Final[Optional[MatchSpec]] = _set_match_spec()

    def get_original_dependency_str(self) -> str:
        """
        TODO
        """
        return self._raw_s

    def get_rendered_dependency_str(self) -> str:
        """
        TODO
        """
        return self._raw_s if self._sub_s is None else self._sub_s

    def has_match_spec(self) -> bool:
        """
        TODO
        """
        return self._match_spec is not None

    def get_match_spec(self) -> MatchSpec:
        """
        TODO
        :raises KeyError: If an underlying `MatchSpec` instance cannot be created for this dependency.
        """
        if self._match_spec is None:
            raise KeyError
        return self._match_spec

    def __eq__(self, o: object) -> bool:
        """
        Checks to see if two objects are equivalent.

        :param o: Other instance to check.
        :returns: True if two `DependencyData` instances are equivalent. False otherwise.
        """
        if not isinstance(o, DependencyData):
            return False
        return self._raw_s == o._raw_s and self._sub_s == self._sub_s

    def __hash__(self) -> int:
        """
        Hashes this `DependencyData` instance.

        :returns: The hash value of this object.
        """
        return hash(self._raw_s)


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
    # Parsed dependency. Identifies a name and version constraints
    data: DependencyData
    # The selector applied to this dependency, if applicable
    selector: Optional[SelectorParser] = None


# Maps-out dependencies found in a recipe. Maps package name -> list of parsed dependencies.
DependencyMap = dict[str, list[Dependency]]
