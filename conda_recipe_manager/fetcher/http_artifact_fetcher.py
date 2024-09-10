"""
:Description: TODO
"""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

from conda_recipe_manager.fetcher.artifact_fetcher import BaseArtifactFetcher


class ArtifactArchiveType(Enum):
    """
    TODO
    """

    ZIP = auto()
    # TODO determine how to do this in Python
    ZIP_7 = auto()  # 7zip
    TARBALL = auto()
    DIRECTORY = auto()  # Uncompressed artifact directory


class HttpArtifactFetcher(BaseArtifactFetcher):

    def __init__(self, name: str, src_url: str):
        """
        TODO
        """
        # TODO derive the name based on the package
        super().__init__(name)
        self._src_url = src_url

    def _extract(self) -> None:
        """
        TODO
        """
        return Path()

    def fetch(self) -> None:
        """
        TODO
        """
        self._extract()

    def get_sha256(self) -> str:
        """
        TODO
        """
        # TODO this does not appear to apply to git-based repos
        return ""

    def get_path_to_uncompressed_artifact() -> Path:
        """
        TODO
        """
        return Path()
