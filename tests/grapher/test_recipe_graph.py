"""
:Description: Unit tests for the RecipeGraph class.
"""

from __future__ import annotations

import pytest

from tests.file_loading import load_recipe_graph


@pytest.mark.parametrize(
    "files,expected",
    [
        ([], False),
        (["simple-recipe_to_str.out"], False),  # Empty from invalid recipe file
        (["types-toml.yaml"], True),
        (["types-toml.yaml", "boto.yaml"], True),
    ],
)
def test_bool_op(files: list[str], expected: bool) -> None:
    """
    Validates the "truthy evaluation" of a RecipeGraph instance
    """
    rg = load_recipe_graph(files)
    assert bool(rg) == expected
