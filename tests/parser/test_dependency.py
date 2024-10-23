"""
:Description: Unit tests for the dependency module.
"""

from __future__ import annotations

import pytest
from conda.models.match_spec import MatchSpec

from conda_recipe_manager.parser.dependency import (
    DependencyData,
    DependencySection,
    DependencyVariable,
    dependency_data_from_str,
    dependency_data_render_as_str,
    dependency_section_to_str,
    str_to_dependency_section,
)
from conda_recipe_manager.parser.types import SchemaVersion


@pytest.mark.parametrize(
    "section,schema,expected",
    [
        (DependencySection.BUILD, SchemaVersion.V0, "build"),
        (DependencySection.HOST, SchemaVersion.V0, "host"),
        (DependencySection.RUN, SchemaVersion.V0, "run"),
        (DependencySection.RUN_CONSTRAINTS, SchemaVersion.V0, "run_constrained"),
        (DependencySection.RUN_EXPORTS, SchemaVersion.V0, "run_exports"),
        (DependencySection.TESTS, SchemaVersion.V0, "requires"),
        (DependencySection.BUILD, SchemaVersion.V1, "build"),
        (DependencySection.HOST, SchemaVersion.V1, "host"),
        (DependencySection.RUN, SchemaVersion.V1, "run"),
        (DependencySection.RUN_CONSTRAINTS, SchemaVersion.V1, "run_constraints"),
        (DependencySection.RUN_EXPORTS, SchemaVersion.V1, "run_exports"),
        (DependencySection.TESTS, SchemaVersion.V1, "requires"),
    ],
)
def test_dependency_section_to_str(section: DependencySection, schema: SchemaVersion, expected: str) -> None:
    """
    Validates deserializing dependency enumerations to strings found in the recipe.

    :param section: Enumeration to deserialize
    :param schema: Target schema
    :param expected: Expected value to return
    """
    assert dependency_section_to_str(section, schema) == expected


@pytest.mark.parametrize(
    "s,expected",
    [
        ("build", DependencySection.BUILD),
        ("host", DependencySection.HOST),
        ("run", DependencySection.RUN),
        ("run_constrained", DependencySection.RUN_CONSTRAINTS),
        ("run_constraints", DependencySection.RUN_CONSTRAINTS),
        ("run_exports", DependencySection.RUN_EXPORTS),
        ("requires", DependencySection.TESTS),
        # Sanitization
        ("  HoSt  ", DependencySection.HOST),
        ("\trun_EXPORTs\t  ", DependencySection.RUN_EXPORTS),
        # Failure cases
        ("foobar", None),
    ],
)
def test_str_to_dependency_section(s: str, expected: DependencySection) -> None:
    """
    Validates serializing dependency section headers to enumerations.

    :param s: String to serialize
    :param expected: Expected value to return
    """
    assert str_to_dependency_section(s) == expected


@pytest.mark.parametrize(
    "s,expected",
    [
        ("openssl", MatchSpec("openssl")),
        ("openssl >=4.2.1", MatchSpec("openssl >=4.2.1")),
        # V0 Format
        ("{{ numpy }}", DependencyVariable("{{ numpy }}")),
        ("{{ compiler('cxx') }}", DependencyVariable("{{ compiler('cxx') }}")),
        # V1 Format
        ("${{ numpy }}", DependencyVariable("${{ numpy }}")),
        ("${{ compiler('cxx') }}", DependencyVariable("${{ compiler('cxx') }}")),
        # Check for resilience (fall-back to `DependencyVariable` type).
        ("foo: {-{ bar }}", DependencyVariable("foo: {-{ bar }}")),
    ],
)
def test_dependency_data_from_str(s: str, expected: DependencyData) -> None:
    """
    Validates the ability to construct `DependencyData` objects from strings.

    :param s: String to construct an object with
    :param expected: Expected value to return
    """
    assert dependency_data_from_str(s) == expected  # type: ignore[misc]


@pytest.mark.parametrize(
    "d,expected",
    [
        (MatchSpec("openssl"), "openssl"),
        (MatchSpec("openssl >=4.2.1"), "openssl >=4.2.1"),
        # V0 Format
        (DependencyVariable("{{ numpy }}"), "{{ numpy }}"),
        (DependencyVariable("{{ compiler('cxx') }}"), "{{ compiler('cxx') }}"),
        # V1 Format
        (DependencyVariable("${{ compiler('cxx') }}"), "${{ compiler('cxx') }}"),
        (DependencyVariable("${{ numpy }}"), "${{ numpy }}"),
        # Check for resilience (fall-back to `DependencyVariable` type).
        (DependencyVariable("foo: {-{ bar }}"), "foo: {-{ bar }}"),
    ],
)
def test_dependency_data_render_as_str(d: DependencyData, expected: str) -> None:
    """
    Validates the ability to return the original string that constructed a `DependencyData` object.

    :param d: DependencyData object used to retrieve the original string
    :param expected: Expected value to return
    """
    assert dependency_data_render_as_str(d) == expected
