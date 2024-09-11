"""
:Description: Provides hashing utilities.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Final

# Default buffer size to use with hashing algorithms.
_HASH_BUFFER_SIZE: Final[int] = 65536  # 64KiB


def hash_str(s: str, hash_algo: Callable[[bytes], hashlib._Hash], encoding: str = "utf-8") -> str:
    """
    Hashes an in-memory string with the given algorithm and returns the hash as a hexadecimal string.

    :param s: Target string.
    :param hash_algo: Hash algorithm function defined provided by `hashlib`. For example pass-in `hashlib.sha256` to
        to perform a SHA-256 hash.
    :param encoding: (Optional) String encoding to use when interpreting the string as bytes. Defaults to `utf-8`.
    :returns: The hash of the string contents, as a hexadecimal string.
    """
    # If the string is small enough to fit in memory, we should not need to worry about buffering it.
    return hash_algo(s.encode(encoding=encoding)).hexdigest()


def hash_file(file: str | Path, hash_algo: str | Callable[[], hashlib._Hash]) -> str:
    """
    Hashes a file from disk with the given algorithm and returns the hash as a hexadecimal string.

    :param file: Target file.
    :param hash_algo: Hash algorithm function defined provided by `hashlib`. This can be a string name recognized by
       `hashlib` or a reference to a hash constructor.
    :returns: The hash of the file, as a hexadecimal string.
    """
    # As of Python 3.11, this is the preferred approach. Prior to this we would have had to roll-our-own buffering
    # scheme.
    with open(file, "rb") as fptr:
        return hashlib.file_digest(fptr, hash_algo).hexdigest()
