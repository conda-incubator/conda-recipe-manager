"""
:Description: Tests for the advanced dependency tools for the `RecipeParser`.
"""

from __future__ import annotations

from typing import Optional

import pytest
from conda.models.match_spec import MatchSpec

from conda_recipe_manager.parser.dependency import Dependency, DependencyConflictMode, DependencySection
from conda_recipe_manager.parser.enums import SelectorConflictMode
from conda_recipe_manager.parser.recipe_parser_deps import RecipeParserDeps
from conda_recipe_manager.parser.selector_parser import SchemaVersion, SelectorParser
from tests.file_loading import load_recipe


@pytest.mark.parametrize(
    "file,dep,dep_mode,sel_mode,expected_return,dep_path,expected_deps,sel_path,expected_sel",
    [
        # Default behavior, add a new dependency, no selector
        (
            "types-toml.yaml",
            Dependency("types-toml", "/requirements/run/0", DependencySection.RUN, MatchSpec("openssl >= 1.4.2"), None),
            DependencyConflictMode.REPLACE,
            SelectorConflictMode.REPLACE,
            True,
            "/requirements/run",
            ["python", "openssl >= 1.4.2"],
            "/requirements/run/1",
            None,
        ),
        # Default behavior, add a new dependency, with a selector
        (
            "types-toml.yaml",
            Dependency(
                "types-toml",
                "/requirements/run/0",
                DependencySection.RUN,
                MatchSpec("openssl >= 1.4.2"),
                SelectorParser("[osx and unix]", SchemaVersion.V0),
            ),
            DependencyConflictMode.REPLACE,
            SelectorConflictMode.REPLACE,
            True,
            "/requirements/run",
            ["python", "openssl >= 1.4.2"],
            "/requirements/run/1",
            "[osx and unix]",
        ),
        # TODO multi-output.
        # TODO add missing paths
        # TODO add v1 support
    ],
)
def test_add_dependency(
    file: str,
    dep: Dependency,
    dep_mode: DependencyConflictMode,
    sel_mode: SelectorConflictMode,
    expected_return: bool,
    dep_path: str,
    expected_deps: list[str],
    sel_path: str,
    expected_sel: Optional[str],
) -> None:
    """
    Tests the ability to add a `Dependency` object to a recipe.

    :param file: File to test against
    :param expected_return: Expected return value
    :param expected_file: Text file containing expected rendered recipe
    """
    parser = load_recipe(file, RecipeParserDeps)
    assert parser.add_dependency(dep, dep_mode=dep_mode, sel_mode=sel_mode) == expected_return

    assert parser.get_value(dep_path) == expected_deps
    # Branch to perform different checks, depending if a selector is expected or not.
    if expected_sel is None:
        with pytest.raises(KeyError):
            parser.get_selector_at_path(sel_path)
    else:
        assert parser.get_selector_at_path(sel_path) == expected_sel
