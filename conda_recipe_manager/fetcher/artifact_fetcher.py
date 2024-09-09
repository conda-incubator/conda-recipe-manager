"""
:Description: TODO
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.fetcher.enums import ArtifactArchiveType

# Identifying string used to flag temp files and directories created by this module.
_ARTIFACT_FETCHER_FILE_ID: Final[str] = "crm_artifact_fetcher"

class ArtifactFetcher:
    """
    TODO
    """

    def __init__(self, source_location: str) -> None:
        """
        TODO
        """
        # TODO
        self._source_location = source_location
        self._temp_dir = tempfile.TemporaryDirectory(suffix=_ARTIFACT_FETCHER_FILE_ID)
        # TODO parse this
        self._type = ArtifactArchiveType.TARBALL

    @staticmethod
    def from_recipe(recipe: RecipeParser) -> list[ArtifactFetcher]:
        """
        TODO construct from a recipe file directly
        """
        sources: list[ArtifactFetcher] = []
        return sources

    def _extract(self) -> None:
        """
        TODO
        """
        return Path()

    def get_sha255(self) -> str:
        """
        TODO
        """
        return ""

    def fetch() -> None:
        """
        TODO
        """
        pass

    def get_path_to_uncompressed_artifact() -> Path:
        """
        TODO
        """
        return Path()