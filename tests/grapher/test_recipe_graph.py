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
        (["v1_format/v1_types-toml.yaml", "v1_format/v1_boto.yaml"], True),
    ],
)
def test_bool_op(files: list[str], expected: bool) -> None:
    """
    Validates the "truthy evaluation" of a RecipeGraph instance
    """
    rg = load_recipe_graph(files)
    assert bool(rg) == expected


@pytest.mark.parametrize(
    "files,package,expected",
    [
        ([], "types-toml", False),
        (["types-toml.yaml"], "types-toml", True),
        (["boto.yaml"], "types-toml", False),
        (["types-toml.yaml", "boto.yaml"], "types-toml", True),
        (["types-toml.yaml", "boto.yaml"], "boto", True),
        # Multi-output
        (["types-toml.yaml", "boto.yaml", "cctools-ld64"], "types-toml", True),
        (["types-toml.yaml", "boto.yaml", "cctools-ld64"], "boto", True),
        # TODO Fix multi-output look-up
        # (["types-toml.yaml", "boto.yaml", "cctools-ld64"], "cctools", True),
        # (["types-toml.yaml", "boto.yaml", "cctools-ld64"], "ld64", True),
        (["types-toml.yaml", "boto.yaml", "cctools-ld64"], "foobar", False),
        # V1
        (["v1_format/v1_types-toml.yaml", "v1_format/v1_boto.yaml"], "types-toml", True),
        (["v1_format/v1_types-toml.yaml", "v1_format/v1_boto.yaml"], "boto", True),
        # TODO V1 multi-output
        # (["v1_format/v1_types-toml.yaml", "v1_format/v1_boto.yaml", "v1_format/v1_cctools-ld64"], "cctools", True),
    ],
)
def test_contains_package_name(files: list[str], package: str, expected: bool) -> None:
    """
    Validates package name checking in a RecipeGraph.
    """
    rg = load_recipe_graph(files)
    assert rg.contains_package_name(package) == expected
