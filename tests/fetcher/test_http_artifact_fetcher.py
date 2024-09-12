"""
:Description: Unit tests for the `HttpArtifactFetcher` class. NOTE: All tests in this file should use `pyfakefs` to
    prevent writing to disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast
from unittest.mock import patch

import pytest

from conda_recipe_manager.fetcher.exceptions import FetchError, FetchRequiredError
from conda_recipe_manager.fetcher.http_artifact_fetcher import HttpArtifactFetcher
from tests.file_loading import TEST_FILES_PATH
from tests.http_mocking import MockHttpStreamResponse


class MockUrl:
    """
    Namespace for mocked URLs
    """

    # URL base to use for "working" endpoints. Allows for easy comparisons in tests.
    URL_BASE: Final[str] = "https://this-is-a-test.anaconda.com/foo/bar/baz/"

    DUMMY_PROJECT_0_TAR_URL: Final[str] = f"{URL_BASE}dummy_project_01.tar.gz"
    DUMMY_PROJECT_0_ZIP_URL: Final[str] = f"{URL_BASE}dummy_project_01.zip"

    # Failed URL
    HTTP_500: Final[str] = f"{URL_BASE}dummy_failure.zip"


@pytest.fixture(
    name="http_fetcher",
    params=[
        ("dummy_project_tar", MockUrl.DUMMY_PROJECT_0_TAR_URL),
        ("dummy_project_zip", MockUrl.DUMMY_PROJECT_0_ZIP_URL),
    ],
)
def fixture_http_fetcher(request: pytest.FixtureRequest) -> HttpArtifactFetcher:
    """
    Parameterized `HttpArtifactFetcher` test fixture.

    :param request: Contains parameters to pass to the constructor.
    """
    return HttpArtifactFetcher(request.param[0], request.param[1])  # type: ignore[misc]


@pytest.fixture(name="http_fetcher_failure")
def fixture_http_fetcher_failure() -> HttpArtifactFetcher:
    """
    Single-instance `HttpArtifactFetcher` test fixture. This can be used for error cases that don't need multiple tests
    to be run or need to simulate a failed HTTP request.
    """
    return HttpArtifactFetcher("dummy_project_failure", MockUrl.HTTP_500)


def mock_requests_get(*args: tuple[str], **_: dict[str, str | int]) -> MockHttpStreamResponse:
    """
    Mocking function for HTTP requests made in this test file.

    :param args: Arguments passed to the `requests.get()`
    :param _: Name-specified arguments passed to `requests.get()` (Unused)
    """
    endpoint = cast(str, args[0])
    match endpoint:
        case MockUrl.DUMMY_PROJECT_0_TAR_URL:
            return MockHttpStreamResponse(200, "archive_files/dummy_project_01.tar.gz")
        case MockUrl.DUMMY_PROJECT_0_ZIP_URL:
            return MockHttpStreamResponse(200, "archive_files/dummy_project_01.zip")
        case MockUrl.HTTP_500:
            return MockHttpStreamResponse(500, "archive_files/dummy_project_01.tar.gz")
        case _:
            # TODO fix: pyfakefs does include `/dev/null` by default, but this actually points to `<temp_dir>/dev/null`
            return MockHttpStreamResponse(404, "/dev/null")


def test_fetch(fs: pytest.Function, http_fetcher: HttpArtifactFetcher) -> None:
    """
    Tests fetching and extracting a software archive.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher: HttpArtifactFetcher test fixture
    """
    # Make the test directory accessible to the HTTP mocker
    fs.add_real_directory(TEST_FILES_PATH)  # type: ignore[attr-defined]

    with patch("requests.get", new=mock_requests_get):
        http_fetcher.fetch()

    # Validate the state of the file system. We must use the private path variable as the directory path changes on
    # every run.
    temp_dir_path: Final[Path] = http_fetcher._temp_dir_path  # pylint: disable=protected-access
    assert temp_dir_path.exists()

    file_name: Final[str] = http_fetcher._archive_url.replace(MockUrl.URL_BASE, "")  # pylint: disable=protected-access
    assert Path(temp_dir_path / file_name).exists()
    assert Path(temp_dir_path / f"extracted_{file_name}/homer.py").exists()
    assert Path(temp_dir_path / f"extracted_{file_name}/README.md").exists()


def test_fetch_file_io_failure(
    fs: pytest.Function, http_fetcher_failure: HttpArtifactFetcher  # pylint: disable=unused-argument
) -> None:
    """
    Tests that a file I/O error raises the correct exception.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_failure: HttpArtifactFetcher test fixture
    """
    # NOTE: We deliberately don't add the test file to the fake file system to force a file error.
    with pytest.raises(FetchError) as e:
        with patch("requests.get", new=mock_requests_get):
            http_fetcher_failure.fetch()

    assert str(e.value) == "A file system error occurred while fetching the archive."


def test_fetch_http_failure(fs: pytest.Function, http_fetcher_failure: HttpArtifactFetcher) -> None:
    """
    Tests that an HTTP error raises the correct exception.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_failure: HttpArtifactFetcher test fixture
    """
    fs.add_real_directory(TEST_FILES_PATH)  # type: ignore[attr-defined]

    with pytest.raises(FetchError) as e:
        with patch("requests.get", new=mock_requests_get):
            http_fetcher_failure.fetch()

    assert str(e.value) == "An HTTP error occurred while fetching the archive."


def test_get_path_to_source_code_raises_no_fetch(
    fs: pytest.Function, http_fetcher_failure: HttpArtifactFetcher  # pylint: disable=unused-argument
) -> None:
    """
    Ensures `get_path_to_source_code()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_failure: HttpArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        http_fetcher_failure.get_path_to_source_code()


def test_get_archive_sha256_raises_no_fetch(
    fs: pytest.Function, http_fetcher_failure: HttpArtifactFetcher  # pylint: disable=unused-argument
) -> None:
    """
    Ensures `get_archive_sha256()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_failure: HttpArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        http_fetcher_failure.get_archive_sha256()


def test_get_archive_type_raises_no_fetch(
    fs: pytest.Function, http_fetcher_failure: HttpArtifactFetcher  # pylint: disable=unused-argument
) -> None:
    """
    Ensures `get_archive_type()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_failure: HttpArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        http_fetcher_failure.get_archive_type()
