"""
:Description: TODO
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import NamedTuple

from conda_recipe_manager.types import DependencyType


class ProjectDependency(NamedTuple):
    """
    A dependency found by scanning a software project's files.

    Not to be confused with `conda_recipe_manager.parser.dependency.Dependency`.
    """

    name: str
    type: DependencyType


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
    def scan(self) -> set[ProjectDependency]:
        """
        TODO
        """
