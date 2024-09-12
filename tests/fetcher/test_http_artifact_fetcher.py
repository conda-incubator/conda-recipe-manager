"""
:Description: TODO
"""

from __future__ import annotations

from typing import Final

import pytest

from conda_recipe_manager.fetcher.exceptions import FetchRequiredError
from conda_recipe_manager.fetcher.http_artifact_fetcher import HttpArtifactFetcher

_DUMMY_PROJECT_0_TAR_URL: Final[str] = "https://this-is-a-test.anaconda.com/foo/bar/baz/dummy_project_01.tar.gz"
_DUMMY_PROJECT_0_ZIP_URL: Final[str] = "https://this-is-a-test.anaconda.com/foo/bar/baz/dummy_project_01.zip"


@pytest.fixture(
    params=[("dummy_project_tar", _DUMMY_PROJECT_0_TAR_URL), ("dummy_project_zip", _DUMMY_PROJECT_0_ZIP_URL)]
)
def http_fetcher(request: pytest.FixtureRequest) -> HttpArtifactFetcher:
    """
    Parameterized `HttpArtifactFetcher` test fixture.

    :param request: Contains parameters to pass to the constructor.
    """
    return HttpArtifactFetcher(request.param[0], request.param[1])


@pytest.fixture()
def http_fetcher_single(request: pytest.FixtureRequest) -> HttpArtifactFetcher:
    """
    Single-instance `HttpArtifactFetcher` test fixture. This can be used for error cases that don't need multiple tests
    to be run.
    """
    return HttpArtifactFetcher("dummy_project_tar", _DUMMY_PROJECT_0_TAR_URL)


def test_fetch(fs: pytest.Function, http_fetcher: HttpArtifactFetcher) -> None:
    """
    Tests fetching and extracting a software archive.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher: HttpArtifactFetcher test fixture
    """
    fetcher = HttpArtifactFetcher("dummy_project", _DUMMY_PROJECT_0_TAR_URL)
    fetcher.fetch()


def test_get_path_to_source_code_raises_no_fetch(fs: pytest.Function, http_fetcher_single: HttpArtifactFetcher) -> None:
    """
    Ensures `get_path_to_source_code()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_single: HttpArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        http_fetcher_single.get_path_to_source_code()


def test_get_archive_sha256_raises_no_fetch(fs: pytest.Function, http_fetcher_single: HttpArtifactFetcher) -> None:
    """
    Ensures `get_archive_sha256()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_single: HttpArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        http_fetcher_single.get_archive_sha256()


def test_get_archive_type_raises_no_fetch(fs: pytest.Function, http_fetcher_single: HttpArtifactFetcher) -> None:
    """
    Ensures `get_archive_type()` throws if `fetch()` has not been called.

    :param fs: pyfakefs fixture used to replace the file system
    :param http_fetcher_single: HttpArtifactFetcher test fixture
    """
    with pytest.raises(FetchRequiredError):
        http_fetcher_single.get_archive_type()
