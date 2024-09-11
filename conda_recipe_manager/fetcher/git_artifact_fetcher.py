"""
:Description: Provides an Artifact Fetcher capable of acquiring source code from a remote git repository.
"""

from __future__ import annotations

from pathlib import Path

from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher


class GitArtifactFetcher(BaseArtifactFetcher):

    def __init__(self, name: str, git_url: str):
        """
        TODO
        TODO add other params
        """
        super().__init__(name)
        self._git_url = git_url

    def _clone() -> None:
        """
        TODO
        """
        pass

    def fetch(self) -> None:
        """
        TODO
        """
        self._clone()

    def get_path_to_source_code(self) -> Path:
        """
        Returns the directory containing the artifact's bundled source code.

        :raises FetchRequiredError: If a call to `fetch()` is required before using this function.
        """
        return Path()
