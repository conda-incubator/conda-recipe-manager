"""
:Description: Constants and utilities used for loading files/recipes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from conda_recipe_manager.grapher.recipe_graph import RecipeGraph
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.recipe_parser_convert import RecipeParserConvert
from conda_recipe_manager.parser.recipe_parser_deps import RecipeParserDeps

# Path to supplementary files used in test cases
TEST_FILES_PATH: Final[Path] = Path(__file__).parent / "test_aux_files"


def load_file(file: Path | str) -> str:
    """
    Loads a file into a single string

    :param file: Filename of the file to read
    :returns: Text from the file
    """
    return Path(file).read_text(encoding="utf-8")


def load_recipe(file_name: str) -> RecipeParser:
    """
    Convenience function that simplifies initializing a recipe parser.

    :param file_name: File name of the test recipe to load
    :returns: RecipeParser instance, based on the file
    """
    recipe = load_file(TEST_FILES_PATH / file_name)
    return RecipeParser(recipe)


def load_recipe_convert(file_name: str) -> RecipeParserConvert:
    """
    Convenience function that simplifies initializing a recipe parser.

    :param file_name: File name of the test recipe to load
    :returns: RecipeParserConvert instance, based on the file
    """
    recipe = load_file(TEST_FILES_PATH / file_name)
    return RecipeParserConvert(recipe)


def load_recipe_deps(file_name: str) -> RecipeParserDeps:
    """
    Convenience function that simplifies initializing a recipe parser.

    :param file_name: File name of the test recipe to load
    :returns: RecipeParserDeps instance, based on the file
    """
    recipe = load_file(TEST_FILES_PATH / file_name)
    return RecipeParserDeps(recipe)


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
            path = f"{TEST_FILES_PATH}/{recipe}"
            parser = RecipeParserDeps(load_file(path))
            tbl[parser.calc_sha256()] = parser
        except Exception:  # pylint: disable=broad-exception-caught
            failed.add(path)

    return RecipeGraph(tbl, failed)
