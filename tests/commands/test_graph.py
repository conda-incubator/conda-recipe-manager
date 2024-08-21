"""
:Description: Tests the `graph` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.graph import graph


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(graph, [])
    assert result.exit_code != 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(graph, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
