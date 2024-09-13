"""
:Description: Tests the `rattler-bulk-build` CLI
"""

from conda_recipe_manager.commands.rattler_bulk_build import rattler_bulk_build
from tests.smoke_testing import assert_cli_usage


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(rattler_bulk_build)
