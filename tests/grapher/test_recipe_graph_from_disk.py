"""
:Description: Unit tests for generating a RecipeGraph from disk storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from conda_recipe_manager.grapher.recipe_graph_from_disk import RecipeGraphFromDisk
from tests.file_loading import get_test_path


def test_construct_rg_from_disk() -> None:
    """
    Simple smoke test that validates constructing a RecipeGraphFromDisk object from a small test directory
    """
    path: Final[Path] = get_test_path() / "rg_from_disk_test"
    # Using all available CPUs WHILE running tests with xdist causes some stability issues. When running tests,
    # pytest-cov will report coverage file corruption AND this test will hang for a few seconds.
    rg = RecipeGraphFromDisk(path, cpu_count=1)
    assert rg.contains_package_name("boto")
    assert rg.contains_package_name("types-toml")
    assert rg.contains_package_name("cctools")
    assert rg.contains_package_name("ld64")
    assert rg.contains_package_name("git-src")
