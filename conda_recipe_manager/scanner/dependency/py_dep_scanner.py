"""
:Description: TODO
"""

from __future__ import annotations

import ast
import pkgutil

# TODO filter with sys.stdlib_module_names
import sys
from pathlib import Path
from typing import Final

from conda_recipe_manager.scanner.dependency.base_dep_scanner import BaseDependencyScanner, Dependency


class PythonDependencyScanner(BaseDependencyScanner):
    """
    TODO
    """

    def __init__(self, src_dir: Path | str):
        """
        TODO
        """
        super().__init__()
        self._src_dir: Final[Path] = Path(src_dir)


    def _get_project_modules(self) -> set[Dependency]:
        """
        TODO
        """
        return {name for _, name, _ in pkgutil.iter_modules([self._src_dir])}

    def _scan_one_file(self, file: Path) -> set[Dependency]:
        """
        TODO
        """
        deps: set[Dependency] = set()
        project_modules: Final[set[Dependency]] = self._get_project_modules()
        # Adapted from:
        #   https://stackoverflow.com/questions/9008451/python-easy-way-to-read-all-import-statements-from-py-module
        root = ast.parse(file.read_text(), file)

        print(__file__)
        for node in ast.walk(root):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            module_name = ""
            if isinstance(node, ast.Import):
                module_name = node.names[0].name.split(".")[0]
            else:
                print(node.module)
                module_name = node.module.split(".")[0]

            # TODO filter relative imports
            # Filter-out the standard library modules and local module names (i.e. modules defined in the target
            # project).
            if not module_name or module_name in sys.stdlib_module_names or module_name in project_modules:
                continue

            deps.add(Dependency(module_name))

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
            except Exception as e:  # pylint: disable=broad-exception
                # TODO log?
                continue

        return all_imports
