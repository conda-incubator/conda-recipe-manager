"""
File:           test_recipe_parser_deps.py
Description:    Tests for the advanced dependency tools for the Recipe Parser.
"""

from __future__ import annotations

import pytest
from conda.models.match_spec import MatchSpec

from conda_recipe_manager.parser.dependency import Dependency, DependencyMap, DependencySection
from conda_recipe_manager.parser.selector_parser import SchemaVersion, SelectorParser
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
        # simple-recipe.yaml tests that unrecognized requirements fields are ignored
        (
            "simple-recipe.yaml",
            {
                "types-toml": [
                    Dependency(
                        "types-toml",
                        "/requirements/host/0",
                        DependencySection.HOST,
                        MatchSpec("setuptools"),
                        SelectorParser("[unix]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "types-toml",
                        "/requirements/host/1",
                        DependencySection.HOST,
                        MatchSpec("fakereq"),
                        SelectorParser("[unix]", SchemaVersion.V0),
                    ),
                    Dependency("types-toml", "/requirements/run/0", DependencySection.RUN, MatchSpec("python"), None),
                ]
            },
        ),
        (
            "boto.yaml",
            {
                "boto": [
                    Dependency("boto", "/requirements/host/0", DependencySection.HOST, MatchSpec("python"), None),
                    Dependency("boto", "/requirements/run/0", DependencySection.RUN, MatchSpec("python"), None),
                ]
            },
        ),
        (
            "v1_format/v1_boto.yaml",
            {
                "boto": [
                    Dependency("boto", "/requirements/host/0", DependencySection.HOST, MatchSpec("python"), None),
                    Dependency("boto", "/requirements/run/0", DependencySection.RUN, MatchSpec("python"), None),
                ]
            },
        ),
        # TODO Future: Add V1 variant of this test when V1 selector support is added.
        (
            "cctools-ld64.yaml",
            {
                "cctools-and-ld64": [
                    Dependency(
                        "cctools-and-ld64",
                        "/requirements/build/0",
                        DependencySection.BUILD,
                        MatchSpec("gcc_{{ native_compiler_subdir }}"),
                        SelectorParser("[linux]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "cctools-and-ld64",
                        "/requirements/build/1",
                        DependencySection.BUILD,
                        MatchSpec("gxx_{{ native_compiler_subdir }}"),
                        SelectorParser("[linux]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "cctools-and-ld64",
                        "/requirements/build/2",
                        DependencySection.BUILD,
                        MatchSpec("autoconf"),
                        None,
                    ),
                    Dependency(
                        "cctools-and-ld64",
                        "/requirements/build/3",
                        DependencySection.BUILD,
                        MatchSpec("automake"),
                        None,
                    ),
                    Dependency(
                        "cctools-and-ld64",
                        "/requirements/host/0",
                        DependencySection.HOST,
                        MatchSpec("xar-bootstrap"),
                        None,
                    ),
                    Dependency(
                        "cctools-and-ld64", "/requirements/host/1", DependencySection.HOST, MatchSpec("zlib"), None
                    ),
                    Dependency(
                        "cctools-and-ld64",
                        "/requirements/host/2",
                        DependencySection.HOST,
                        MatchSpec("llvm-lto-tapi"),
                        None,
                    ),
                ],
                "cctools": [
                    Dependency(
                        "cctools",
                        "/outputs/0/requirements/run/0",
                        DependencySection.RUN,
                        MatchSpec("llvm-lto-tapi"),
                        None,
                    ),
                    Dependency(
                        "cctools",
                        "/requirements/build/0",
                        DependencySection.BUILD,
                        MatchSpec("gcc_{{ native_compiler_subdir }}"),
                        SelectorParser("[linux]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "cctools",
                        "/requirements/build/1",
                        DependencySection.BUILD,
                        MatchSpec("gxx_{{ native_compiler_subdir }}"),
                        SelectorParser("[linux]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "cctools", "/requirements/build/2", DependencySection.BUILD, MatchSpec("autoconf"), None
                    ),
                    Dependency(
                        "cctools", "/requirements/build/3", DependencySection.BUILD, MatchSpec("automake"), None
                    ),
                    Dependency(
                        "cctools", "/requirements/host/0", DependencySection.HOST, MatchSpec("xar-bootstrap"), None
                    ),
                    Dependency("cctools", "/requirements/host/1", DependencySection.HOST, MatchSpec("zlib"), None),
                    Dependency(
                        "cctools", "/requirements/host/2", DependencySection.HOST, MatchSpec("llvm-lto-tapi"), None
                    ),
                ],
                "ld64": [
                    Dependency(
                        "ld64",
                        "/outputs/1/requirements/host/0",
                        DependencySection.HOST,
                        MatchSpec("llvm-lto-tapi"),
                        None,
                    ),
                    Dependency(
                        "ld64",
                        "/outputs/1/requirements/host/1",
                        DependencySection.HOST,
                        MatchSpec("libcxx"),
                        SelectorParser("[osx]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "ld64", "/outputs/1/requirements/run/0", DependencySection.RUN, MatchSpec("llvm-lto-tapi"), None
                    ),
                    Dependency(
                        "ld64",
                        "/outputs/1/requirements/run/1",
                        DependencySection.RUN,
                        MatchSpec("libcxx"),
                        SelectorParser("[osx]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "ld64",
                        "/requirements/build/0",
                        DependencySection.BUILD,
                        MatchSpec("gcc_{{ native_compiler_subdir }}"),
                        SelectorParser("[linux]", SchemaVersion.V0),
                    ),
                    Dependency(
                        "ld64",
                        "/requirements/build/1",
                        DependencySection.BUILD,
                        MatchSpec("gxx_{{ native_compiler_subdir }}"),
                        SelectorParser("[linux]", SchemaVersion.V0),
                    ),
                    Dependency("ld64", "/requirements/build/2", DependencySection.BUILD, MatchSpec("autoconf"), None),
                    Dependency("ld64", "/requirements/build/3", DependencySection.BUILD, MatchSpec("automake"), None),
                    Dependency(
                        "ld64", "/requirements/host/0", DependencySection.HOST, MatchSpec("xar-bootstrap"), None
                    ),
                    Dependency("ld64", "/requirements/host/1", DependencySection.HOST, MatchSpec("zlib"), None),
                    Dependency(
                        "ld64", "/requirements/host/2", DependencySection.HOST, MatchSpec("llvm-lto-tapi"), None
                    ),
                ],
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
