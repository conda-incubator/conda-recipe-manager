"""
:Description: Provides classes for mocking HTTP responses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import requests

from conda_recipe_manager.types import JsonType, SentinelType
from tests.file_loading import get_test_path, load_file, load_json_file


class MockHttpResponse:
    """
    Class that mocks a basic HTTP response.
    """

    def __init__(self, status_code: int, content_type: str = "text/plain"):
        """
        Constructs a mocked HTTP response. This is the base class for more advanced mockers.

        :param status_code: HTTP status code to return
        :param content_type: (Optional) `content-type` header string
        """
        self.headers = {"content-type": content_type}
        self.status_code = status_code


class MockHttpTextResponse(MockHttpResponse):
    """
    Class that mocks a basic text HTTP response.
    """

    _sentinel = SentinelType()

    def __init__(
        self,
        status_code: int,
        content_type: str = "text/plain",
        file: Path | str = "",
        data: str | SentinelType = _sentinel,
    ):
        """
        Constructs a mocked HTTP response that returns text data.

        :param status_code: HTTP status code to return
        :param content_type: (Optional) `content-type` header string
        :param file: (Optional) Path to a file whose contents should be returned as text
        :param data: (Optional) Text to return, as a string
        """
        super().__init__(status_code, content_type)

        if file:
            self.text = load_file(file)
        else:
            self.text = "" if isinstance(data, SentinelType) else data


class MockHttpJsonResponse(MockHttpResponse):
    """
    Class that mocks an HTTP response with a JSON payload.

    Originally developed for:
      https://github.com/anaconda/anaconda-packaging-utils/blob/main/anaconda_packaging_utils/tests/testing_utils.py
    """

    _sentinel = SentinelType()

    def __init__(self, status_code: int, json_file: Path | str = "", json_data: JsonType | SentinelType = _sentinel):
        """
        Constructs a mocked HTTP response that returns JSON.

        :param status_code: HTTP status code to return
        :param json_file: (Optional) Path to file to load JSON data from.
        :param json_data: (Optional) If `json_file` is unspecified, this value can set the JSON payload directly.
        """
        super().__init__(status_code, "application/json")

        if json_file:
            self.json_data = load_json_file(json_file)
        else:
            self.json_data = {} if isinstance(json_data, SentinelType) else json_data

    def json(self) -> JsonType:
        """
        Mocked function call that returns JSON data.

        :returns: Parsed JSON data
        """
        return self.json_data


class MockHttpStreamResponse(MockHttpResponse):
    """
    Class that mocks an HTTP response that streams data. Simulates large file downloads.
    """

    def __init__(
        self,
        status_code: int,
        file: Path | str,
        content_type: str = "application/zip",
    ):
        """
        Constructs a mocked HTTP response that streams data.

        NOTE: `fs.add_real_directory()` must be called before this mocker is used in order to ensure
        the file is available to the fake file system.

        :param status_code: HTTP status code to return
        :param file: Path to file to load data from.
        :param content_type: (Optional) `content-type` header string
        """
        super().__init__(status_code, content_type)
        self._file_obj = open(get_test_path() / file, "rb")  # pylint: disable=consider-using-with

        # Mock `iter_content()` by passing the buck to `read()`
        def _mock_iter_content(chunk_size: int) -> Iterable[bytes]:
            # Simulate an exception if a non-200 error code is provided
            if self.status_code // 100 != 2:
                raise requests.exceptions.ConnectionError("Simulated failure!")
            yield self._file_obj.read(chunk_size)

        self.iter_content = _mock_iter_content

    def __del__(self) -> None:
        """
        Destructor for the HTTP mocker. Cleans up file pointer to test file.
        """
        # `_file_obj` may not exist if `open()` threw an exception.
        if hasattr(self, "_file_obj"):
            self._file_obj.close()
