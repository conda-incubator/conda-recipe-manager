"""
:Description: Provides an Artifact Fetcher capable of acquiring source code from a remote git repository.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, NamedTuple, Optional

from git import Repo

from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher


class _GitTarget(NamedTuple):
    """
    Convenience structure that contains all the information to target a `git` repo at a point in time.
    """

    url: str
    branch: Optional[str] = None
    tag: Optional[str] = None
    rev: Optional[str] = None


class GitArtifactFetcher(BaseArtifactFetcher):
    """
    Artifact Fetcher capable of cloning a remote git repository.
    """

    def __init__(
        self, name: str, url: str, branch: Optional[str] = None, tag: Optional[str] = None, rev: Optional[str] = None
    ):
        """
        Constructs a `GitArtifactFetcher` instance.

        :param name: Identifies the artifact. Ideally, this is the package name. In multi-sourced/mirrored scenarios,
            this might be the package name combined with some identifying information.
        :param url: Remote or local path to the target repository
        :param branch: (Optional) Target git branch name
        :param tag: (Optional) Target git tag name
        :param rev: (Optional) Target git revision ID
        """
        super().__init__(name)

        self._is_remote = not Path(url).exists()
        self._git_target = _GitTarget(
            url=url,
            branch=branch,
            tag=tag,
            rev=rev,
        )

    def _clone(self) -> Repo:
        """
        TODO
        """
        # TODO exception handling
        match self._is_remote:
            case True:
                return Repo.clone_from(self._git_target.url, self._temp_dir_path)  # type: ignore[misc]
            case False:
                shutil.copytree(self._git_target.url, self._temp_dir_path)
                return Repo(self._temp_dir_path)

    def fetch(self) -> None:
        """
        TODO
        """
        repo: Final[Repo] = self._clone()
        # TODO checkout branch/tag/rev
        self._successfully_fetched = True

    def get_path_to_source_code(self) -> Path:
        """
        Returns the directory containing the artifact's bundled source code.

        :raises FetchRequiredError: If a call to `fetch()` is required before using this function.
        """
        self._fetch_guard("Repository has not been cloned, so the source code is unavailable.")

        # TODO figure out top-level folder to append
        return self._temp_dir_path
