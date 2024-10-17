"""
:Description: Tests the `bump-recipe` CLI
"""

from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands import bump_recipe
from tests.file_loading import get_test_path, load_file
from tests.smoke_testing import assert_cli_usage
from tests.file_loading import get_test_path
from conda_recipe_manager.commands.utils.types import ExitCode


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

    result = runner.invoke(bump_recipe.bump_recipe, [str(recipe_file_path)])
    assert result.exit_code==ExitCode.SUCCESS


def test_bump_recipe_cli_fails(fs: FakeFilesystem) -> None:
    """
    Test for the case when build number is not an integer
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)
    
    recipe_file_path = get_test_path()/"bump_recipe/non-int-build-num.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, [str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


    