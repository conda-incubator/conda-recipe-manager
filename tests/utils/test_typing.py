"""
:Description: Tests the typing utility module.
"""

from __future__ import annotations

from typing import Optional

import pytest

from conda_recipe_manager.types import JsonType
from conda_recipe_manager.utils.typing import optional_str


@pytest.mark.parametrize(
    "val,expected",
    [
        (42, "42"),
        (4.2, "4.2"),
        (False, "False"),
        (None, None),
        ("null", "null"),
        ("foobar", "foobar"),
        ({"foo": "bar"}, "{'foo': 'bar'}"),
        ([1, 2, 3, 4, 5], "[1, 2, 3, 4, 5]"),
    ],
)
def test_optional_str(val: JsonType, expected: Optional[str]) -> None:
    """


    :param val: Value to convert
    :param expected: Expected result of the test
    """
    assert optional_str(val) == expected
