"""
:Description: Tests the `graph` CLI
"""

from conda_recipe_manager.commands.graph import graph
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(graph)
