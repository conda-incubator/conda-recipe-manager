"""
:Description: Unit tests for the SelectorParser class
"""

from __future__ import annotations

import pytest

from conda_recipe_manager.parser.enums import SchemaVersion
from conda_recipe_manager.parser.platform_types import Platform
from conda_recipe_manager.parser.selector_parser import SelectorParser


@pytest.mark.parametrize(
    "selector,schema,expected",
    [
        ("", SchemaVersion.V0, "Schema: V0 | Tree: None"),
        ("[]", SchemaVersion.V0, "Schema: V0 | Tree: None"),
        ("osx", SchemaVersion.V0, "Schema: V0 | Tree: osx"),
        ("[osx]", SchemaVersion.V0, "Schema: V0 | Tree: osx"),
        ("[not osx]", SchemaVersion.V0, "Schema: V0 | Tree: not L osx"),
        ("[not osx and unix]", SchemaVersion.V0, "Schema: V0 | Tree: and L not L osx R unix"),
        ("[osx and not unix]", SchemaVersion.V0, "Schema: V0 | Tree: and L osx R not L unix"),
        ("[osx and py37]", SchemaVersion.V0, "Schema: V0 | Tree: and L osx R py37"),
    ],
)
def test_selector_parser_construction(selector: str, schema: SchemaVersion, expected: str) -> None:
    """
    Tests the construction of a selector parse tree by comparing the debug string representation of the tree.
    :param selector: Selector string to parse
    :param schema: Target schema version
    :param expected: Expected value to return
    """
    parser = SelectorParser(selector, schema)
    assert str(parser) == expected
    assert not parser.is_modified()


@pytest.mark.parametrize(
    "selector,schema,expected",
    [
        ("", SchemaVersion.V0, set()),
        ("[]", SchemaVersion.V0, set()),
        ("osx", SchemaVersion.V0, {Platform.OSX_64, Platform.OSX_ARM_64}),
        ("[osx]", SchemaVersion.V0, {Platform.OSX_64, Platform.OSX_ARM_64}),
        (
            "[not osx]",
            SchemaVersion.V0,
            {
                Platform.LINUX_32,
                Platform.LINUX_64,
                Platform.LINUX_AARCH_64,
                Platform.LINUX_ARM_V6L,
                Platform.LINUX_ARM_V7L,
                Platform.LINUX_PPC_64,
                Platform.LINUX_PPC_64_LE,
                Platform.LINUX_RISC_V64,
                Platform.LINUX_SYS_390,
                Platform.WIN_32,
                Platform.WIN_64,
                Platform.WIN_ARM_64,
            },
        ),
        (
            "[not osx and unix]",
            SchemaVersion.V0,
            {
                Platform.LINUX_32,
                Platform.LINUX_64,
                Platform.LINUX_AARCH_64,
                Platform.LINUX_ARM_V6L,
                Platform.LINUX_ARM_V7L,
                Platform.LINUX_PPC_64,
                Platform.LINUX_PPC_64_LE,
                Platform.LINUX_RISC_V64,
                Platform.LINUX_SYS_390,
            },
        ),
        (
            "[not osx or unix]",
            SchemaVersion.V0,
            {
                Platform.LINUX_32,
                Platform.LINUX_64,
                Platform.LINUX_AARCH_64,
                Platform.LINUX_ARM_V6L,
                Platform.LINUX_ARM_V7L,
                Platform.LINUX_PPC_64,
                Platform.LINUX_PPC_64_LE,
                Platform.LINUX_RISC_V64,
                Platform.LINUX_SYS_390,
                # OSX is included in the UNIX category, therefore it is included
                Platform.OSX_64,
                Platform.OSX_ARM_64,
                Platform.WIN_32,
                Platform.WIN_64,
                Platform.WIN_ARM_64,
            },
        ),
        ("[osx and not unix]", SchemaVersion.V0, set()),
        # TODO FIX: Python versions should have no effect on which Platforms are included
        # ("[osx and py37]", SchemaVersion.V0, {Platform.OSX_64, Platform.OSX_ARM_64}),
        ("[osx or py37]", SchemaVersion.V0, {Platform.OSX_64, Platform.OSX_ARM_64}),
        ("[win and not x86]", SchemaVersion.V0, {Platform.WIN_ARM_64}),
        # NOTE: Conda appears to treat PowerPC-64 as incompatible with PowerPC-64-LE
        (
            "[ppc64 or win]",
            SchemaVersion.V0,
            {Platform.WIN_32, Platform.WIN_64, Platform.WIN_ARM_64, Platform.LINUX_PPC_64},
        ),
        ("[linux-armv7l]", SchemaVersion.V0, {Platform.LINUX_ARM_V7L}),
        (
            "[linux-armv6l or win]",
            SchemaVersion.V0,
            {Platform.LINUX_ARM_V6L, Platform.WIN_32, Platform.WIN_64, Platform.WIN_ARM_64},
        ),
    ],
)
def test_get_selected_platforms(selector: str, schema: SchemaVersion, expected: set[Platform]) -> None:
    """
    Tests the construction of a selector parse tree by comparing the debug string representation of the tree.
    :param selector: Selector string to parse
    :param schema: Target schema version
    :param expected: Expected value to return
    """
    parser = SelectorParser(selector, schema)
    assert parser.get_selected_platforms() == expected
    assert not parser.is_modified()
