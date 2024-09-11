"""
:Description: TODO
"""

from __future__ import annotations

from typing import Final, cast

from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import Primitives

# Identifying string used to flag temp files and directories created by this module.
_ARTIFACT_FETCHER_FILE_ID: Final[str] = "crm_artifact_fetcher"


def from_recipe(recipe: RecipeParser) -> list[BaseArtifactFetcher]:
    """
    TODO Complete: construct from a recipe file directly
    """
    sources: list[BaseArtifactFetcher] = []
    # TODO add source-specific parser?
    parsed_sources = cast(dict[str, Primitives] | list[dict[str, Primitives]], recipe.get_value("/source"))
    if not isinstance(parsed_sources, list):
        parsed_sources = [parsed_sources]

    for _ in parsed_sources:
        pass
    return sources
