"""
:Description: TODO
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from conda_recipe_manager.scanner.dependency.base_dep_scanner import BaseDependencyScanner, Dependency

# TODO filter with sys.stdlib_module_names
# import sys


class PythonDependencyScanner(BaseDependencyScanner):
    """
    TODO
    """

    def __init__(self, src_dir: Path):
        """
        TODO
        """
        super().__init__()
        self._src_dir: Final[Path] = src_dir

    def scan(self) -> list[Dependency]:
        """
        TODO
        """
        return []
