"""
:Description: TODO
"""

from __future__ import annotations

from typing import Final

from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser

# Identifying string used to flag temp files and directories created by this module.
_ARTIFACT_FETCHER_FILE_ID: Final[str] = "crm_artifact_fetcher"


def from_recipe(recipe: RecipeParser) -> list[BaseArtifactFetcher]:
    """
    TODO Complete: construct from a recipe file directly
    """
    sources: list[BaseArtifactFetcher] = []
    # TODO add source-specific parser?
    parsed_sources = recipe.get_value("/source")
    for _ in parsed_sources:
        pass
    return sources
