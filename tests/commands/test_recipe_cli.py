"""
File:           test_recipe_cli.py
Description:    Tests the recipe CLI
"""
from click.testing import CliRunner

from percy.commands.recipe import recipe


def test_usage() -> None:
    """
    Ensure failure to provide a sub-command results in rendering the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(recipe, [])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(recipe, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
