"""
:Description: Unit tests for the RecipeGraph class.
"""

from __future__ import annotations

import pytest

from conda_recipe_manager.grapher.types import PackageStats
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
        (["types-toml.yaml", "boto.yaml", "cctools-ld64.yaml"], "types-toml", True),
        (["types-toml.yaml", "boto.yaml", "cctools-ld64.yaml"], "boto", True),
        (["types-toml.yaml", "boto.yaml", "cctools-ld64.yaml"], "cctools", True),
        (["types-toml.yaml", "boto.yaml", "cctools-ld64.yaml"], "ld64", True),
        (["types-toml.yaml", "boto.yaml", "cctools-ld64.yaml"], "foobar", False),
        # V1
        (["v1_format/v1_types-toml.yaml", "v1_format/v1_boto.yaml"], "types-toml", True),
        (["v1_format/v1_types-toml.yaml", "v1_format/v1_boto.yaml"], "boto", True),
        # TODO V1 multi-output
    ],
)
def test_contains_package_name(files: list[str], package: str, expected: bool) -> None:
    """
    Validates package name checking in a RecipeGraph.
    """
    rg = load_recipe_graph(files)
    assert rg.contains_package_name(package) == expected


@pytest.mark.parametrize(
    "files,expected",
    [
        ([], PackageStats()),
        (
            ["types-toml.yaml", "boto.yaml", "cctools-ld64.yaml"],
            PackageStats(total_parsed_recipes=3, total_recipes=3, total_packages=5),
        ),
    ],
)
def test_package_stats(files: list[str], expected: PackageStats) -> None:
    """
    Validates gathering package statistics in a RecipeGraph.
    """
    rg = load_recipe_graph(files)
    assert rg.get_package_stats() == expected
