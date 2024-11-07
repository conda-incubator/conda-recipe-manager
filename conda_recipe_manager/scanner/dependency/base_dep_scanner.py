"""
:Description: Provides a base class for all dependency scanners to be derived from.
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import NamedTuple

from conda_recipe_manager.parser.dependency import DependencySection
from conda_recipe_manager.types import MessageTable


class ProjectDependency(NamedTuple):
    """
    A dependency found by scanning a software project's files.

    Not to be confused with `conda_recipe_manager.parser.dependency.Dependency`.
    """

    name: str
    type: DependencySection


class BaseDependencyScanner(metaclass=ABCMeta):
    """
    Base class for all Dependency Scanner classes.
    """

    def __init__(self) -> None:
        """
        Constructs a `BaseDependencyScanner`.
        """
        self._msg_tbl = MessageTable()

    @abstractmethod
    def scan(self) -> set[ProjectDependency]:
        """
        Actively scans a project for dependencies. Implementation is dependent on the type of scanner used.

        :returns: A set of unique dependencies found by the scanner.
        """

    def get_message_table(self) -> MessageTable:
        """
        Returns the internal message table.

        :returns: Message table object containing logged messages.
        """
        return self._msg_tbl
