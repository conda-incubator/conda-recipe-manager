"""
:Description: Tests the `patch` CLI
"""

from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands.patch import patch
from conda_recipe_manager.commands.utils.types import ExitCode
from tests.file_loading import get_test_path
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(patch)


def test_patch_cli_faulty_patch(fs: FakeFilesystem) -> None:
    """
    Test to check that patch operation fails with a patch that cannot be applied.

    :param fs: pyfakefs fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    json_patch_path = get_test_path() / "patch/json_patch.json"
    bad_recipe_file_path = get_test_path() / "patch/bad_recipe.yaml"

    result = runner.invoke(patch, [str(json_patch_path), str(bad_recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_patch_cli_faulty_json_patch_file(fs: FakeFilesystem) -> None:
    """
    Test to check the patch operation fails with a invalid JSON patch file

    :param fs: pyfakefs fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    faulty_json_patch_path = get_test_path() / "patch" / "bad_json_patch.json"
    recipe_file_path = get_test_path() / "patch" / "recipe.yaml"

    result = runner.invoke(patch, [str(faulty_json_patch_path), str(recipe_file_path)])
    # this JSON_ERROR comes after
    assert result.exit_code == ExitCode.JSON_ERROR


def test_patch_cli(fs: FakeFilesystem) -> None:
    """
    Test to check the case when both the recipe file and the JSON patch file are in the correct format and read-able.

    :param fs: pyfakefs fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    json_patch_path = get_test_path() / "patch" / "json_patch.json"
    recipe_file_path = get_test_path() / "patch" / "recipe.yaml"

    result = runner.invoke(patch, [str(json_patch_path), str(recipe_file_path)])
    assert result.exit_code == ExitCode.SUCCESS
