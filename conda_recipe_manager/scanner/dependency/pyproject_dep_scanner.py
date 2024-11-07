"""
:Description: TODO
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final, cast

from conda_recipe_manager.parser.dependency import DependencySection
from conda_recipe_manager.scanner.dependency.base_dep_scanner import BaseDependencyScanner, ProjectDependency


class PyProjectDependencyScanner(BaseDependencyScanner):
    """
    Dependency Scanner class capable of scanning `pyproject.toml` files.
    """

    def __init__(self, src_dir: Path | str):
        """
        Constructs a `PyProjectDependencyScanner`.

        :param src_dir: Path to the Python source code to scan.
        """
        super().__init__()
        self._src_dir: Final[Path] = Path(src_dir)

    def scan(self) -> set[ProjectDependency]:
        """
        Actively scans a project for dependencies. Implementation is dependent on the type of scanner used.

        :returns: A set of unique dependencies found by the scanner.
        """
        # TODO handle malformed `pyproject.toml` exceptions
        # TODO perform schema check against `pyproject.toml`
        with open(self._src_dir / "pyproject.toml", "rb") as f:
            data = cast(dict[str, dict[str, list[str] | dict[str, list[str]]]], tomllib.load(f))

        # TODO matchspec equivalency
        deps: set[ProjectDependency] = set()
        for dep_name in cast(list[str], data["project"]["dependencies"]):
            deps.add(ProjectDependency(dep_name, DependencySection.RUN))

        # Optional dependencies are stored in a dictionary, where the key is the "package extra" name and the value is
        # a dependency list. For example: {'dev': ['pytest'], 'conda_build': ['conda-build']}
        for dep_lst in cast(dict[str, list[str]], data["project"]["optional-dependencies"]).values():
            for dep_name in dep_lst:
                deps.add(ProjectDependency(dep_name, DependencySection.RUN_CONSTRAINTS))

        return deps
