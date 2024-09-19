"""
:Description: TODO
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import NamedTuple, Optional


class Dependency(NamedTuple):
    """
    TODO
    """

    name: str


class BaseDependencyScanner(metaclass=ABCMeta):
    """
    TODO
    """

    def __init__(self) -> None:
        """
        TODO
        """
        pass

    @abstractmethod
    def scan(self) -> set[Dependency]:
        """
        TODO
        """
