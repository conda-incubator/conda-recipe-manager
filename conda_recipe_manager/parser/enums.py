"""
File:           enums.py
Description:    Provides enumerated types used by the parser.
"""

from __future__ import annotations

from enum import Enum, IntEnum, StrEnum


class SchemaVersion(IntEnum):
    """
    Recipe `schema_version` enumeration. The Pre-CEP-13 "schema" is designated as "Version 0" and does not require
    a `schema_version` field in the recipe file.
    """

    V0 = 0  # Pre-CEP-13, effectively defined by conda-build
    V1 = 1  # CEP-13+


class SelectorConflictMode(Enum):
    """
    Defines how to handle the addition of a selector if one already exists.
    """

    AND = 1  # Logically "and" the new selector with the old
    OR = 2  # Logically "or" the new selector with the old
    REPLACE = 3  # Replace the existing selector


class LogicOp(StrEnum):
    """
    Logic operators used in selector syntax
    """

    AND = "and"
    OR = "or"
    NOT = "not"


class Platform(StrEnum):
    """
    Platforms/architectures/operating systems/sub directories recognized by conda
    Derived from:
      - https://github.com/conda/conda-build/blob/6b222c76ac0ba3b9f2efaf2f807ed335a3b46c00/conda_build/cli/main_convert.py#L63
      - https://github.com/conda/conda-build/blob/6b222c76ac0ba3b9f2efaf2f807ed335a3b46c00/tests/test_metadata.py#L485
    """

    ## Generic ##
    UNIX = "unix"
    LINUX = "linux"
    OSX = "osx"
    WINDOWS = "win"
    ## Specific ##
    # TODO add more
    # ("emscripten-wasm32", {"unix", "emscripten", "wasm32"}),
    # ("wasi-wasm32", {"wasi", "wasm32"}),
    # ("freebsd-64", {"freebsd", "x86", "x86_64"}),
    # ("linux-32", {"unix", "linux", "linux32", "x86"}),
    # ("linux-64", {"unix", "linux", "linux64", "x86", "x86_64"}),
    # ("linux-aarch64", {"unix", "linux", "aarch64"}),
    # ("linux-armv6l", {"unix", "linux", "arm", "armv6l"}),
    # ("linux-armv7l", {"unix", "linux", "arm", "armv7l"}),
    # ("linux-ppc64", {"unix", "linux", "ppc64"}),
    # ("linux-ppc64le", {"unix", "linux", "ppc64le"}),
    # ("linux-riscv64", {"unix", "linux", "riscv64"}),
    # ("linux-s390x", {"unix", "linux", "s390x"}),
    # ("osx-64", {"unix", "osx", "x86", "x86_64"}),
    # ("osx-arm64", {"unix", "osx", "arm64"}),
    # ("win-32", {"win", "win32", "x86"}),
    # ("win-64", {"win", "win64", "x86", "x86_64"}),
    # ("win-arm64", {"win", "arm64"}),
    # ("zos-z", {"zos", "z"}),
