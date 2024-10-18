"""
:Description: Tests the `bump-recipe` CLI
"""

from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands import bump_recipe
from conda_recipe_manager.commands.utils.types import ExitCode
from tests.file_loading import get_test_path
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(bump_recipe.bump_recipe)


def test_bump_recipe_cli(fs: FakeFilesystem) -> None:
    """
    Test for the case when build number is successfully incremented by 1.
    :param fs: pyfakefs fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "simple-recipe.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_recipe_cli_fails(fs: FakeFilesystem) -> None:
    """
    Test for the case when build number is not an integer
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/non-int-build-num.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_build_num_key_not_found(fs: FakeFilesystem) -> None:
    """
    Test for the case when build number key is not found in the recipe file.
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no-build-num.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION
