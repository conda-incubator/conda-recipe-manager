"""
File:           test_main_cli.py
Description:    Tests the primary CLI interface, found under `percy.commands.main`
"""
from click.testing import CliRunner

from percy.commands.main import cli


def test_usage() -> None:
    """
    Ensure failure to provide a sub-command results in rendering the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
