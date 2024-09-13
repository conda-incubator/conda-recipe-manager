"""
:Description: Tests the `patch` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.patch import patch


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(patch, [])
    assert result.exit_code != 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(patch, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
