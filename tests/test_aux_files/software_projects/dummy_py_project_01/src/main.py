"""
:Description: Main entry point of this dummy Python project used for unit testing.
"""

import hashlib

from src.dummy_module import meaning_of_life  # type: ignore[import-not-found]

from conda_recipe_manager.utils.cryptography.hashing import hash_str


def main() -> None:
    print("Hello, foobar!")
    meaning_of_life()
    print(hash_str("foobar", hashlib.sha256))


if __name__ == "__main__":
    main()
