"""
:Description: Tests the `bump-recipe` CLI
"""

from typing import Final

import pytest
from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands import bump_recipe
from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from tests.file_loading import get_test_path, load_recipe
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(bump_recipe.bump_recipe)


@pytest.mark.parametrize(
    "recipe_file, increment_build_num, expected_recipe_file",
    [
        ("simple-recipe.yaml", True, "bump_recipe/build_num_1.yaml"),
        ("simple-recipe.yaml", False, "simple-recipe.yaml"),
        ("bump_recipe/build_num_1.yaml", True, "bump_recipe/build_num_2.yaml"),
        ("bump_recipe/build_num_1.yaml", False, "simple-recipe.yaml"),
        ("bump_recipe/build_num_42.yaml", True, "bump_recipe/build_num_43.yaml"),
        ("bump_recipe/build_num_42.yaml", False, "simple-recipe.yaml"),
        ("bump_recipe/build_num_-1.yaml", True, "simple-recipe.yaml"),
        ("bump_recipe/build_num_-1.yaml", False, "simple-recipe.yaml"),
    ],
)
def test_bump_recipe_cli(
    fs: FakeFilesystem, recipe_file: str, increment_build_num: bool, expected_recipe_file: str
) -> None:
    """
    Test that the build number is successfully reset to 0.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / recipe_file
    expected_recipe_file_path = get_test_path() / expected_recipe_file

    cli_args: Final[list[str]] = (
        ["--build-num", str(recipe_file_path)] if increment_build_num else [str(recipe_file_path)]
    )
    result = runner.invoke(bump_recipe.bump_recipe, cli_args)

    parser = load_recipe(recipe_file_path, RecipeParser)
    expected_parser = load_recipe(expected_recipe_file_path, RecipeParser)

    assert parser == expected_parser
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_cli_build_number_key_missing(fs: FakeFilesystem) -> None:
    """
    Test that a `build: number:` key is added and set to 0 when it's missing.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_num.yaml"
    expected_recipe_file_path = get_test_path() / "bump_recipe/build_num_added.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, [str(recipe_file_path)])

    parser = load_recipe(recipe_file_path, RecipeParser)
    expected_parser = load_recipe(expected_recipe_file_path, RecipeParser)

    assert parser == expected_parser
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_cli_build_num_not_int(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully case when the build number is not an integer,
    and we are trying to increment it.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/non_int_build_num.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_bump_cli_build_numb_key_not_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully when the build number key is missing and we try to increment it's value.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_num.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_bump_cli_no_build_key_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully when the build key is missing and we try to revert build number to zero.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_key.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, [str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION
