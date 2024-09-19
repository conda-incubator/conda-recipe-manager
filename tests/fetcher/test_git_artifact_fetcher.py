"""
:Description: Unit tests for the `GitArtifactFetcher` class.

:Note:
  - All tests in this file should use `pyfakefs` to prevent writing to disk.
  - `GitPython` is incompatible with `pyfakefs` as it relies on the `git` CLI.
    Since the `GitArtifactFetcher` class is a simple wrapper around `GitPython`,
    the amount of mocking compared to the amount of lines tested makes the cost
    of developing comprehensive unit tests high compared to the value received.
  - TODO Future: develop an integration test for this class against `GitPython`
"""

from __future__ import annotations

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.fetcher.exceptions import FetchRequiredError
from conda_recipe_manager.fetcher.git_artifact_fetcher import GitArtifactFetcher


@pytest.fixture(name="git_fetcher_failure")
def fixture_git_fetcher_failure() -> GitArtifactFetcher:
    """
    Single-instance `GitArtifactFetcher` test fixture. This can be used for error cases that don't need multiple tests
    to be run or need to simulate a failed git command.
    """
    return GitArtifactFetcher("dummy_project_failure", "")


def test_get_path_to_source_code_raises_no_fetch(
    fs: FakeFilesystem,  # pylint: disable=unused-argument
    git_fetcher_failure: GitArtifactFetcher,
) -> None:
    """
    Ensures `get_path_to_source_code()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param git_fetcher_failure: GitArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        git_fetcher_failure.get_path_to_source_code()
