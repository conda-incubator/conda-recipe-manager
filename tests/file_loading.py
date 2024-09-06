"""
:Description: Constants and utilities used for loading files/recipes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Type, TypeVar

from conda_recipe_manager.grapher.recipe_graph import RecipeGraph
from conda_recipe_manager.parser.recipe_parser_deps import RecipeParserDeps
from conda_recipe_manager.parser.recipe_reader import RecipeReader

# Path to supplementary files used in test cases
TEST_FILES_PATH: Final[Path] = Path(__file__).parent / "test_aux_files"

# Generic Type for recipe-parsing classes
R = TypeVar("R", bound=RecipeReader)


def load_file(file: Path | str) -> str:
    """
    Loads a file into a single string. Assumes the file is under the `TEST_FILES_PATH` directory, which is the standard
    location for all testing files.

    :param file: Filename/relative path of the file to read
    :returns: Text from the file
    """
    return Path(TEST_FILES_PATH / file).read_text(encoding="utf-8")


def load_recipe(file_name: str, recipe_parser: Type[R]) -> R:
    """
    Convenience function that simplifies initializing a recipe parser.

    :param file_name: File name of the test recipe to load
    :returns: RecipeParser instance, based on the file
    """
    recipe = load_file(file_name)
    return recipe_parser(recipe)


def load_recipe_graph(recipes: list[str]) -> RecipeGraph:
    """
    Loads a series of recipe files into a graph.

    :param recipes: List of recipe test files
    :returns: RecipeParser graph consisting of the recipes provided
    """
    tbl: dict[str, RecipeParserDeps] = {}
    failed: set[str] = set()
    for recipe in recipes:
        try:
            parser = RecipeParserDeps(load_file(recipe))
            tbl[parser.calc_sha256()] = parser
        except Exception:  # pylint: disable=broad-exception-caught
            failed.add(recipe)

    return RecipeGraph(tbl, failed)
