"""
:Description: Tests the `patch` CLI
"""

from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands.patch import patch
from conda_recipe_manager.commands.utils.types import ExitCode
from tests.file_loading import TEST_FILES_PATH
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(patch)


def test_patch_cli_faulty_recipe_file(fs: FakeFilesystem) -> None:
    """
    Test to check the patch operation fails with a bad recipe file i.
    a recipe which does not have the correct format etc
    :param fs: the pyfakes library
    """
    runner = CliRunner()
    fs.add_real_directory(TEST_FILES_PATH, read_only=False)  # type: ignore[attr-defined]

    json_patch_path = TEST_FILES_PATH / "patch" / "json_patch.json"
    faulty_recipe_file_path = TEST_FILES_PATH / "patch" / "bad_recipe.yaml"

    result = runner.invoke(patch, [str(json_patch_path), str(faulty_recipe_file_path)])
    # assert pytest.raises(IOError)
    # assert result.exit_code == ExitCode.IO_ERROR
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_patch_cli_faulty_json_patch_file(fs: FakeFilesystem) -> None:
    """
    Test to check the patch operation fails with a invalid JSON patch file
    :param fs: the pyfakes library
    """
    runner = CliRunner()
    fs.add_real_directory(TEST_FILES_PATH, read_only=False)  # type: ignore[attr-defined]

    faulty_json_patch_path = TEST_FILES_PATH / "patch" / "bad_json_patch.json"
    recipe_file_path = TEST_FILES_PATH / "patch" / "recipe.yaml"

    result = runner.invoke(patch, [str(faulty_json_patch_path), str(recipe_file_path)])
    # assert pytest.raises(json.JSONDecodeError)
    assert result.exit_code == ExitCode.JSON_ERROR


def test_patch_cli(fs: FakeFilesystem) -> None:
    """
    Test to check the case when both the recipe file and the JSON patch file are in the correct format and read-able.
    :param fs: the pyfakes library
    """
    runner = CliRunner()
    fs.add_real_directory(TEST_FILES_PATH, read_only=False)  # type: ignore[attr-defined]

    json_patch_path = TEST_FILES_PATH / "patch" / "json_patch.json"
    recipe_file_path = TEST_FILES_PATH / "patch" / "recipe.yaml"

    result = runner.invoke(patch, [str(json_patch_path), str(recipe_file_path)])
    assert result.exit_code == ExitCode.SUCCESS
