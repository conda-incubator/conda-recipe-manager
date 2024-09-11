"""
:Description: TODO
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

# Identifying string used to flag temp files and directories created by this module.
_ARTIFACT_FETCHER_FILE_ID: Final[str] = "crm_artifact_fetcher"


class ArtifactFetcherException(Exception):
    """
    Base exception for all other artifact fetching exceptions. Should not be raised directly.
    """

    pass


class FetchError(ArtifactFetcherException):
    """
    General exception to be thrown when there is a failure to fetch an artifact.
    """

    def __init__(self, message: str):
        """
        Constructs a FetchError Exception.

        :param message: String description of the issue encountered.
        """
        self.message = message if len(message) else "An unknown error occurred while trying to fetch an artifact."
        super().__init__(self.message)


class FetchRequiredError(ArtifactFetcherException):
    """
    This operation could not be performed because a call to `fetch()` has not yet succeeded.
    """

    def __init__(self, message: str):
        """
        Constructs a FetchRequiredError Exception.

        :param message: String description of the issue encountered.
        """
        self.message = (
            message if len(message) else "An operation could not be completed as the artifact has not been fetched."
        )
        super().__init__(self.message)


class BaseArtifactFetcher(metaclass=ABCMeta):
    """
    Base class for all `ArtifactFetcher` classes. An `ArtifactFetcher` provides a standard set of tools to retrieve
    bundles of source code.

    Files retrieved from any artifact fetcher are stored in a secure temporary directory. That directory is deleted
    when the Artifact Fetcher instances falls out of scope.
    """

    def __init__(self, name: str) -> None:
        """
        Constructs a BaseArtifactFetcher.

        :param name: Identifies the artifact. Ideally, this is the package name. In multi-sourced/mirrored scenarios,
            this might be the package name combined with some identifying information.
        """
        self._name = name
        self._temp_dir: Final[TemporaryDirectory] = TemporaryDirectory(prefix=_ARTIFACT_FETCHER_FILE_ID, suffix=name)
        self._temp_dir_path: Final[Path] = Path(self._temp_dir.name)
        # Flag to track if `fetch()` has been called successfully once.
        self._successfully_fetched = False

    @abstractmethod
    def fetch(self) -> None:
        """
        Retrieves the build artifact and source code and dumps it to a secure temporary location.

        "Gretchen, stop trying to make fetch happen! It's not going to happen!" - Regina George

        :raises FetchError: When the target artifact fails to be acquired.
        """
        pass

    @abstractmethod
    def get_path_to_source_code(self) -> Path:
        """
        Returns the directory containing the artifact's bundled source code.

        :raises FetchRequiredError: If a call to `fetch()` is required before using this function.
        """
        pass
