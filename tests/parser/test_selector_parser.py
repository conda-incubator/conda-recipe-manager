"""
File:           test_selector_parser.py
Description:    Unit tests for the RecipeParser class
"""

from __future__ import annotations

import pytest

from conda_recipe_manager.parser.enums import SchemaVersion
from conda_recipe_manager.parser.selector_parser import SelectorParser


@pytest.mark.parametrize(
    "selector,schema,expected",
    [
        ("osx", SchemaVersion.V0, "Schema: V0 | Tree: osx"),
        ("[osx]", SchemaVersion.V0, "Schema: V0 | Tree: osx"),
        ("[not osx]", SchemaVersion.V0, "Schema: V0 | Tree: not L osx"),
        ("[not osx and unix]", SchemaVersion.V0, "Schema: V0 | Tree: and L not L osx R unix"),
        ("[osx and not unix]", SchemaVersion.V0, "Schema: V0 | Tree: and L osx R not L unix"),
    ],
)
def test_selector_parser_construction(selector: str, schema: SchemaVersion, expected: str) -> None:
    """
    Tests the construction of a selector parse tree by comparing the debug string representation of the tree.
    :param selector: Selector string to parse
    :param schema: Target schema version
    :param expected: Expected value to return
    """
    assert str(SelectorParser(selector, schema)) == expected
