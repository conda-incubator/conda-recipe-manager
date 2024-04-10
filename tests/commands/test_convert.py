"""
File:           test_convert_cli.py
Description:    Tests the `convert` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.convert import convert


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(convert, [])
    assert result.exit_code != 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(convert, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
