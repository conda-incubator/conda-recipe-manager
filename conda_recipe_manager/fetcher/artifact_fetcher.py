"""
:Description: TODO
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser

# Identifying string used to flag temp files and directories created by this module.
_ARTIFACT_FETCHER_FILE_ID: Final[str] = "crm_artifact_fetcher"


def from_recipe(recipe: RecipeParser) -> list[BaseArtifactFetcher]:
    """
    TODO construct from a recipe file directly
    """
    sources: list[BaseArtifactFetcher] = []
    return sources
