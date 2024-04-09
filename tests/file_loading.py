"""
File:           file_loading.py
Description:    Constants and utilities used for loading files/recipes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Final

from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.recipe_parser_convert import RecipeParserConvert

# Path to supplementary files used in test cases
TEST_FILES_PATH: Final[Path] = Path(__file__).parent / "test_aux_files"


def load_file(file: Path | str) -> str:
    """
    Loads a file into a single string
    :param file: Filename of the file to read
    :returns: Text from the file
    """
    with open(Path(file), "r", encoding="utf-8") as f:
        return f.read()


def load_recipe(file_name: str) -> RecipeParser:
    """
    Convenience function that simplifies initializing a recipe parser.
    :param file_name: File name of the test recipe to load
    :returns: RecipeParser instance, based on the file
    """
    recipe = load_file(f"{TEST_FILES_PATH}/{file_name}")
    return RecipeParser(recipe)


def load_recipe_convert(file_name: str) -> RecipeParserConvert:
    """
    Convenience function that simplifies initializing a recipe parser.
    :param file_name: File name of the test recipe to load
    :returns: RecipeParserConvert instance, based on the file
    """
    recipe = load_file(f"{TEST_FILES_PATH}/{file_name}")
    return RecipeParserConvert(recipe)
