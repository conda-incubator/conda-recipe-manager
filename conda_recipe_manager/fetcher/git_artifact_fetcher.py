"""
:Description: TODO
"""

from __future__ import annotations

from conda_recipe_manager.fetcher.artifact_fetcher import BaseArtifactFetcher


class HttpArtifactFetcher(BaseArtifactFetcher):

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
