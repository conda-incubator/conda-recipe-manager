"""
:Description: Local dummy module used for unit testing.
"""

import hashlib  # pylint: disable=ignore-unused-import
import math

import requests  # pylint: disable=ignore-unused-import


def meaning_of_life() -> None:
    print(int(math.pow(4, 2)) + 26)
