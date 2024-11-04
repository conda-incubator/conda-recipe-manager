"""
:Description: Tests the `bump-recipe` CLI
"""

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


def test_bump_recipe_cli(fs: FakeFilesystem) -> None:
    """
    Test for the case when build number is successfully incremented by 1.
    :param fs: `pyfakefs` Fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "simple-recipe.yaml"
    incremented_recipe_file_path = get_test_path() / "bump_recipe/incremented_by_one.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])

    parser = load_recipe(recipe_file_path, RecipeParser)
    incremented_parser = load_recipe(incremented_recipe_file_path, RecipeParser)

    assert parser.render() == incremented_parser.render()
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_build_num_not_int(fs: FakeFilesystem) -> None:
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


def test_bump_build_num_key_not_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully when the build number key is missing and we try to increment it's value.
    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_num.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION
