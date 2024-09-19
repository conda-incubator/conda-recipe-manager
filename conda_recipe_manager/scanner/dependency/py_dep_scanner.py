"""
:Description: TODO
"""

from __future__ import annotations

import ast

# TODO filter with sys.stdlib_module_names
import sys
from pathlib import Path
from typing import Final

from conda_recipe_manager.scanner.dependency.base_dep_scanner import BaseDependencyScanner, Dependency


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

    def _scan_one_file(self, file: Path) -> set[Dependency]:
        """
        TODO
        """
        deps: set[Dependency] = set()
        # Adapted from:
        #   https://stackoverflow.com/questions/9008451/python-easy-way-to-read-all-import-statements-from-py-module
        root = ast.parse(file.read_text(), file)

        for node in ast.walk(root):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            # TODO sanitize name. Only care about top-level
            print(f"TODO rm: {n.name}")
            # Filter-out anything in the standard Python library.
            if n.name in sys.stdlib_module_names:
                continue

            for n in node.names:
                # TODO list of modules is unhashable
                deps.add(Dependency(n.name, n.asname))

        return deps

    def scan(self) -> set[Dependency]:
        """
        TODO
        """
        # TODO parallelize
        all_imports: list[Dependency] = set()
        for file in self._src_dir.rglob("*.py"):
            try:
                all_imports |= self._scan_one_file(file)
            except Exception:  # pylint: disable=broad-exception
                # TODO log?
                continue

        return all_imports
