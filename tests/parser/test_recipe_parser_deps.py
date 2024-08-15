"""
File:           test_recipe_parser_deps.py
Description:    Tests for the advanced dependency tools for the Recipe Parser.
"""

from __future__ import annotations

import pytest
from conda.models.match_spec import MatchSpec

from conda_recipe_manager.parser.dependency import Dependency, DependencyMap, DependencySection
from tests.file_loading import load_recipe_deps


@pytest.mark.parametrize(
    "file,expected",
    [
        ("types-toml.yaml", {"types-toml": "/"}),
        ("v1_format/v1_types-toml.yaml", {"types-toml": "/"}),
        ("boto.yaml", {"boto": "/"}),
        ("v1_format/v1_boto.yaml", {"boto": "/"}),
        (
            "google-cloud-cpp.yaml",
            {
                "google-cloud-cpp-split": "/",
                "libgoogle-cloud-all": "/outputs/0",
                "libgoogle-cloud-all-devel": "/outputs/1",
                "google-cloud-cpp": "/outputs/2",
            },
        ),
        (
            "v1_format/v1_google-cloud-cpp.yaml",
            {
                "google-cloud-cpp-split": "/",
                "libgoogle-cloud-all": "/outputs/0",
                "libgoogle-cloud-all-devel": "/outputs/1",
                "google-cloud-cpp": "/outputs/2",
            },
        ),
    ],
)
def test_get_package_names_to_path(file: str, expected: dict[str, str]) -> None:
    """
    :param file: File to test against
    :param expected: Expected output
    """
    parser = load_recipe_deps(file)
    assert parser.get_package_names_to_path() == expected


@pytest.mark.parametrize(
    "file,expected",
    [
        (
            "types-toml.yaml",
            {
                "types-toml": [
                    Dependency(
                        "types-toml", "/requirements/host/0", DependencySection.HOST, MatchSpec("setuptools"), None
                    ),
                    Dependency("types-toml", "/requirements/host/1", DependencySection.HOST, MatchSpec("wheel"), None),
                    Dependency("types-toml", "/requirements/host/2", DependencySection.HOST, MatchSpec("pip"), None),
                    Dependency("types-toml", "/requirements/host/3", DependencySection.HOST, MatchSpec("python"), None),
                    Dependency("types-toml", "/requirements/run/0", DependencySection.RUN, MatchSpec("python"), None),
                ]
            },
        ),
        (
            "v1_format/v1_types-toml.yaml",
            {
                "types-toml": [
                    Dependency(
                        "types-toml", "/requirements/host/0", DependencySection.HOST, MatchSpec("setuptools"), None
                    ),
                    Dependency("types-toml", "/requirements/host/1", DependencySection.HOST, MatchSpec("wheel"), None),
                    Dependency("types-toml", "/requirements/host/2", DependencySection.HOST, MatchSpec("pip"), None),
                    Dependency("types-toml", "/requirements/host/3", DependencySection.HOST, MatchSpec("python"), None),
                    Dependency("types-toml", "/requirements/run/0", DependencySection.RUN, MatchSpec("python"), None),
                ]
            },
        ),
    ],
)
def test_get_all_dependencies(file: str, expected: DependencyMap) -> None:
    """
    :param file: File to test against
    :param expected: Expected output
    """
    parser = load_recipe_deps(file)
    assert parser.get_all_dependencies() == expected
