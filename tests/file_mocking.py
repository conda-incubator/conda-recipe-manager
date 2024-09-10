"""
:Description: Test utility module that provides file mocking tools.
"""

from __future__ import annotations

from typing import Callable, cast
from unittest import mock


class _Writeable:
    """
    Dummy class used to provide type annotations to `return_value` in the object returned by `mock.mock_open()`.
    """

    write: Callable[[str], None]


class MockOpener:
    """
    Dummy class used to provide type annotations to the object returned by `mock.mock_open()`.
    """

    return_value: _Writeable


class MockWriter:
    """
    Mocking class that accumulates text to a buffer to simulate writing to a file.

    Replaces `return_value.write` when using the mocker returned by `mock.mock_open()`.

    Adapted from:
      https://stackoverflow.com/questions/70861340/how-to-check-what-was-written-to-a-mock-open-fake-file
    """

    def __init__(self, init_contents: str = ""):
        """
        Constructs a mocked file that can be written to.

        :param init_contents: (Optional) Initial state of the file to set. Allows for simulating "append to file"
            operations.
        """
        self._contents = init_contents

    def write(self, buff: str) -> None:
        """
        Simulates writing to a file on disk.

        :param buff: String buffer to write to the mocked file.
        """
        self._contents += buff

    def __str__(self) -> str:
        """
        Returns the string representation of this mocked file, which is the file contents.

        :returns: Contents of the mocked file.
        """
        return self._contents

    def __eq__(self, o: object) -> bool:
        """
        Checks to see if two MockWriter instances have the same file contents.

        :param o: Other object to check against
        :returns: True if the two MockWriter instances have the same file contents.
        """
        if not isinstance(o, MockWriter):
            return False
        return str(self) == str(o)

    @staticmethod
    def setup_file_mockers(mocked_data: str) -> tuple[MockOpener, MockWriter]:
        """
        Convenience function that sets up a mocked file opener and a `MockWriter` instance to be used for testing that
        writes the expected `mocked_data` to a file.

        :param mocked_data: Data that should be contained in the file that is being written to.
        :returns: The mock opener and mock writer instances configured to emulate a file that should contain
            `mocked_data`.
        """
        mock_opener = cast(MockOpener, mock.mock_open(read_data=mocked_data))
        mock_writer = MockWriter()
        mock_opener.return_value.write = mock_writer.write
        return mock_opener, mock_writer
