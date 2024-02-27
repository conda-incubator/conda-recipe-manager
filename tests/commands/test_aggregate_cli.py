"""
File:           test_aggregate_cli.py
Description:    Tests the `aggregate` CLI
"""
from click.testing import CliRunner

from percy.commands.aggregate import aggregate


def test_usage() -> None:
    """
    Ensure failure to provide a sub-command results in rendering the help menu
    """
    runner = CliRunner()
    # No commands are provided
    result = runner.invoke(aggregate, [])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
    # Help is specified
    result = runner.invoke(aggregate, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage:")
