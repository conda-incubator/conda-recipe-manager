"""
:Description: Tests the base `conda-recipe-manager` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.conda_recipe_manager import conda_recipe_manager


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(conda_recipe_manager, [])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(conda_recipe_manager, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
