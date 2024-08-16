"""
:Description: Base class that provides basic modification tracking.
"""

from __future__ import annotations


class IsModifiable:
    """
    Base class that represents the ability for a class to track where it has been modified.
    """

    def __init__(self) -> None:
        """
        Constructs a modifiable object that has not been modified.
        """
        self._is_modified = False

    def is_modified(self) -> bool:
        """
        Indicates if the object has been modified.

        :returns: True if the object instance has been modified. False otherwise.
        """
        return self._is_modified
