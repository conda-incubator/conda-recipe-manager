"""
:Description: Provides typing utility functions.
"""

from __future__ import annotations

from typing import Optional

from conda_recipe_manager.types import JsonType


def optional_str(val: JsonType) -> Optional[str]:
    """
    Forces evaluation of a variable to a string or to `None`. In other words, like `str()`, but preserves `None`.

    :param val: Value to convert to a string.
    :returns: String equivalent of a value or None.
    """
    if val is None:
        return None
    return str(val)
