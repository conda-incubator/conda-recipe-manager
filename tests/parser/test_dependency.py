"""
File:           test_dependency.py
Description:    Unit tests for the dependency module.
"""

from __future__ import annotations

import pytest

from conda_recipe_manager.parser.dependency import (
    DependencySection,
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
        (DependencySection.BUILD, SchemaVersion.V1, "build"),
        (DependencySection.HOST, SchemaVersion.V1, "host"),
        (DependencySection.RUN, SchemaVersion.V1, "run"),
        (DependencySection.RUN_CONSTRAINTS, SchemaVersion.V1, "run_constraints"),
        (DependencySection.RUN_EXPORTS, SchemaVersion.V1, "run_exports"),
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
