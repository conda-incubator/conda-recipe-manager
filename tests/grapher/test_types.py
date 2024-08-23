"""
:Description: Unit tests for the grapher types module.
"""

from __future__ import annotations

import json

import pytest

from conda_recipe_manager.grapher.types import PackageStats, PackageStatsEncoder


@pytest.mark.parametrize(
    "stats,expected",
    [
        (
            PackageStats(),
            (
                '{"package_name_duplicates": [],'
                ' "recipes_failed_to_parse": [],'
                ' "recipes_failed_to_parse_dependencies": {},'
                ' "total_parsed_recipes": 0,'
                ' "total_recipes": 0,'
                ' "total_packages": 0}'
            ),
        ),
        (
            PackageStats(total_packages=50, total_parsed_recipes=20, total_recipes=25),
            (
                '{"package_name_duplicates": [],'
                ' "recipes_failed_to_parse": [],'
                ' "recipes_failed_to_parse_dependencies": {},'
                ' "total_parsed_recipes": 20,'
                ' "total_recipes": 25,'
                ' "total_packages": 50}'
            ),
        ),
        (
            PackageStats(
                package_name_duplicates={"foobar"},
                recipes_failed_to_parse={"foo", "bar"},
                recipes_failed_to_parse_dependencies={"charlie": ["tango", "bravo"]},
                total_packages=42,
                total_parsed_recipes=20,
                total_recipes=25,
            ),
            (
                '{"package_name_duplicates": ["foobar"],'
                ' "recipes_failed_to_parse": ["bar", "foo"],'
                ' "recipes_failed_to_parse_dependencies": {"charlie": ["tango", "bravo"]},'
                ' "total_parsed_recipes": 20,'
                ' "total_recipes": 25,'
                ' "total_packages": 42}'
            ),
        ),
    ],
)
def test_package_stats_json_endcoding(stats: PackageStats, expected: str) -> None:
    """
    Validates serializing PackageStats to JSON
    """
    assert json.dumps(stats, cls=PackageStatsEncoder) == expected  # type: ignore[misc]
