"""
:Description: Tests the `convert` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.convert import convert
from tests.file_loading import get_test_path, load_file
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(convert)


def test_only_allow_v0_recipes() -> None:
    """
    Ensures the user gets an error when a V1 recipe is provided to the conversion script.
    """
    runner = CliRunner()
    result = runner.invoke(convert, [str(get_test_path() / "v1_format/v1_simple-recipe.yaml")])
    assert result.exit_code != 0
    assert result.output.startswith("ILLEGAL OPERATION:")


def test_convert_single_file() -> None:
    """
    Ensures the user gets an error when a V1 recipe is provided to the conversion script.
    """
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(convert, [str(get_test_path() / "simple-recipe.yaml")])
    # This recipe has warnings
    assert result.exit_code == 100
    # `crm convert` prints an additional newline
    assert result.stdout == load_file("v1_format/v1_simple-recipe.yaml") + "\n"
