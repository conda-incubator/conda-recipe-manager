"""
:Description: Tests the hashing utility module.
"""

from __future__ import annotations

import hashlib
from typing import Callable

import pytest

from conda_recipe_manager.utils.cryptography.hashing import hash_file, hash_str
from tests.file_loading import TEST_FILES_PATH, load_file


@pytest.mark.parametrize(
    "file,algo,expected",
    [
        ("types-toml.yaml", "sha256", "e117d210da9ea6507fdea856ee96407265aec40cbc58432aa6e1c7e31998a686"),
        ("types-toml.yaml", hashlib.sha256, "e117d210da9ea6507fdea856ee96407265aec40cbc58432aa6e1c7e31998a686"),
        (
            "types-toml.yaml",
            "sha512",
            "0055bcbefb34695caa35e487cdd4e94340ff08db19a3de45a0fb79a270b2cc1f5183b8ebbca018a747e3b3a6fb8ce2a70d090f8510de4712bb24645202d75b36",  # pylint: disable=line-too-long
        ),
    ],
)
def test_hash_file(file: str, algo: str | Callable[[], hashlib._Hash], expected: str) -> None:
    """
    Validates calculating a file's hash with a given algorithm.

    :param file: Target file
    :param algo: Target algorithm
    :param expected: Expected value to return
    """
    assert hash_file(TEST_FILES_PATH / file, algo) == expected


@pytest.mark.parametrize(
    "s,algo,expected",
    [
        ("quick brown fox", hashlib.sha256, "8700be3b2fe64bd5f36be0b194f838c3aa475cbee660601f5acf19c99498d264"),
        (
            "foo bar baz",
            hashlib.sha512,
            "bce50343a56f01dc7cf2d4c82127be4fff3a83ddb8b783b1a28fb6574637ceb71ef594b1f03a8e9b7d754341831292bcad1a3cb8a12fd2ded7a57b1b173b3bf7",  # pylint: disable=line-too-long
        ),
    ],
)
def test_hash_str(s: str, algo: Callable[[bytes], hashlib._Hash], expected: str) -> None:
    """
    Validates calculating a strings's hash with a given algorithm. This tests large strings, so we read from test files.

    :param s: Target string
    :param algo: Target algorithm
    :param expected: Expected value to return
    """

    assert hash_str(s, algo) == expected


@pytest.mark.parametrize(
    "file,algo,expected",
    [
        ("types-toml.yaml", hashlib.sha256, "e117d210da9ea6507fdea856ee96407265aec40cbc58432aa6e1c7e31998a686"),
        (
            "types-toml.yaml",
            hashlib.sha512,
            "0055bcbefb34695caa35e487cdd4e94340ff08db19a3de45a0fb79a270b2cc1f5183b8ebbca018a747e3b3a6fb8ce2a70d090f8510de4712bb24645202d75b36",  # pylint: disable=line-too-long
        ),
    ],
)
def test_hash_str_from_file(file: str, algo: Callable[[bytes], hashlib._Hash], expected: str) -> None:
    """
    Validates calculating a strings's hash with a given algorithm. This tests large strings, so we read from test files.

    :param file: Target file (that the string is read from)
    :param algo: Target algorithm
    :param expected: Expected value to return
    """

    assert hash_str(load_file(file), algo) == expected
