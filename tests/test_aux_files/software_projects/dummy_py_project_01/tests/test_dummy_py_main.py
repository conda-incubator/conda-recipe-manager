"""
:Description: Fake test file to test fake python test dependencies. THIS SHOULD NOT RUN AS A CRM TEST!
"""

import collections  # pylint: disable=ignore-unused-import

import requests  # pylint: disable=ignore-unused-import
import yaml  # pylint: disable=ignore-unused-import


def test_main() -> None:
    """
    Fake test file
    """
    # Guarantees we will know if this test runs accidentally.
    assert False
