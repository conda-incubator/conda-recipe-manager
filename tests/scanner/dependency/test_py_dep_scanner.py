"""
:Description: Provides unit tests for the `PythonDependencyScanner` class.
"""

from pathlib import Path
from typing import Final, cast

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.scanner.dependency.base_dep_scanner import ProjectDependency
from conda_recipe_manager.scanner.dependency.py_dep_scanner import PythonDependencyScanner
from conda_recipe_manager.types import DependencyType
from tests.file_loading import get_test_path


@pytest.mark.parametrize(
    "project_name,expected",
    [
        (
            "dummy_py_project_01",
            {
                ProjectDependency("conda_recipe_manager", DependencyType.RUN),
                ProjectDependency("matplotlib", DependencyType.RUN),  # Two imports on one line
                ProjectDependency("networkx", DependencyType.RUN),  # Two imports on one line
                ProjectDependency("python", DependencyType.HOST),
                ProjectDependency("python", DependencyType.RUN),
                ProjectDependency("pyyaml", DependencyType.TEST),
                ProjectDependency("requests", DependencyType.RUN),  # Found in source and test code.
            },
        ),
    ],
)
def test_scan(project_name: str, expected: set[ProjectDependency], request: pytest.FixtureRequest) -> None:
    """
    Tests scanning for Python dependencies with a mocked-out Python project.

    :param project_name: Name of the dummy Python project directory to use
    :param expected: Expected value
    """
    fs = cast(FakeFilesystem, request.getfixturevalue("fs"))
    project_path: Final[Path] = get_test_path() / "software_projects" / project_name
    fs.add_real_directory(project_path)

    scanner = PythonDependencyScanner(project_path)
    assert scanner.scan() == expected
