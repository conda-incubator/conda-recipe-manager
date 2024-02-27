"""
File:           test_convert_cli.py
Description:    Tests the `convert` CLI
"""
from click.testing import CliRunner

from percy.commands.convert import convert


def test_usage() -> None:
    """
    Ensure failure to provide a sub-command results in rendering the help menu
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
