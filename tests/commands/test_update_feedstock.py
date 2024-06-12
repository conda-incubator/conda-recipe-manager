"""
File:           test_update_feedstock.py
Description:    Tests the `update-feedstock` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.update_feedstock import update_feedstock


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(update_feedstock, [])
    assert result.exit_code != 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(update_feedstock, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
