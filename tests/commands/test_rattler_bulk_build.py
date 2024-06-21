"""
File:           test_rattler_bulk_build.py
Description:    Tests the `rattler-bulk-build` CLI
"""

from click.testing import CliRunner

from conda_recipe_manager.commands.rattler_bulk_build import rattler_bulk_build


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(rattler_bulk_build, [])
    assert result.exit_code != 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(rattler_bulk_build, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
