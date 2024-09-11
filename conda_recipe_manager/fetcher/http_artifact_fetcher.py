"""
:Description: Provides an Artifact Fetcher capable of acquiring a software archive from an HTTP/HTTPS source.
"""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from enum import Enum, auto
from pathlib import Path
from typing import Final

import requests

from conda_recipe_manager.fetcher.base_artifact_fetcher import BaseArtifactFetcher, FetchError, FetchRequiredError
from conda_recipe_manager.types import HASH_BUFFER_SIZE


class ArtifactArchiveType(Enum):
    """
    Enumerates the types of archive file formats that are supported.
    """

    ZIP = auto()
    # TODO determine how to do this in Python
    ZIP_7 = auto()  # 7zip
    TARBALL = auto()
    UNKNOWN = auto()  # Could not determine the artifact type


class HttpArtifactFetcher(BaseArtifactFetcher):
    """
    Artifact Fetcher capable of downloading a software archive from a remote HTTP/HTTPS source.
    """

    def __init__(self, name: str, archive_url: str | Path):
        """
        Constructs an `HttpArtifactFetcher` instance.

        :param name: Identifies the artifact. Ideally, this is the package name. In multi-sourced/mirrored scenarios,
            this might be the package name combined with some identifying information.
        :param archive_url:
        """
        super().__init__(name)
        self._archive_url = Path(archive_url)
        self._archive_type = ArtifactArchiveType.UNKNOWN

        # Reliable, multi-extension removal approach derived from this post:
        #  https://stackoverflow.com/questions/3548673/how-can-i-replace-or-strip-an-extension-from-a-filename-in-python
        archive_name_no_ext: Final[str] = str(self._archive_url).removesuffix("".join(self._archive_url.suffixes))

        self._archive_path: Final[Path] = self._temp_dir_path / self._archive_url.name
        self._uncompressed_archive_path: Final[Path] = self._temp_dir_path / archive_name_no_ext

    def _fetch_guard(self, msg: str) -> None:
        """
        Convenience function that prevents executing functions that require the archive to be downloaded.

        :param msg: Message to attach to the exception.
        :raises FetchRequiredError: If `fetch()` has not been successfully invoked.
        """
        if self._successfully_fetched:
            return
        raise FetchRequiredError(msg)

    def _extract(self) -> None:
        """
        Retrieves the build artifact and source code and dumps it to a secure temporary location.

        :raises FetchError: If an issue occurred while extracting the archive.
        """
        try:
            match self._archive_path:
                case path if tarfile.is_tarfile(path):
                    self._archive_type = ArtifactArchiveType.TARBALL
                    tar_file = tarfile.TarFile(self._archive_path)
                    # The `filter="data"` parameter guards against "the most dangerous security issues"
                    tar_file.extractall(path=self._uncompressed_archive_path, filter="data")
                case path if zipfile.is_zipfile(path):
                    self._archive_type = ArtifactArchiveType.ZIP
                    zip_file = zipfile.ZipFile(self._archive_path)
                    # TODO improve security checks
                    zip_file.extractall(path=self._uncompressed_archive_path)
                # TODO 7-zip support
                case _:
                    raise FetchError("The archive type could not be identified.") from e
        except (tarfile.TarError, zipfile.BadZipFile, ValueError) as e:
            raise FetchError("An extraction error occurred while extracting the archive.") from e
        except IOError as e:
            raise FetchError("A file system error occurred while extracting the archive.") from e

    def fetch(self) -> None:
        """
        Retrieves a software archive from a remote HTTP/HTTPS host and stores the files in a secure temporary directory.

        :raises FetchError: If an issue occurred while downloading or extracting the archive.
        """
        # Buffered download approach
        try:
            response = requests.get(self._archive_url, stream=True)
            with open(self._archive_path, "wb") as archive:
                for chunk in response.iter_content(chunk_size=1024):
                    if not chunk:
                        break
                    archive.write(chunk)
        except requests.exceptions.RequestException as e:
            raise FetchError("An HTTP error occurred while fetching the archive.") from e
        except IOError as e:
            raise FetchError("A file system error occurred while fetching the archive.") from e

        self._extract()

        # If we have not thrown at this point, we have successfully fetched the archive.
        self._successfully_fetched = True

    def get_path_to_source_code(self) -> Path:
        """
        Returns the directory containing the artifact's bundled source code.

        :raises FetchRequiredError: If `fetch()` has not been successfully invoked.
        """
        self._fetch_guard("Archive has not been downloaded, so the source code is unavailable.")

        return self._uncompressed_archive_path

    def get_archive_sha256(self) -> str:
        """
        Calculates a SHA-256 hash on the downloaded software archive.

        :raises FetchRequiredError: If `fetch()` has not been successfully invoked.
        """
        self._fetch_guard("Archive has not been downloaded, so the file can't be hashed.")

        # TODO generalize this buffering as a utility. `recipe_reader.py` could use this.
        sha256 = hashlib.sha256()
        with open(self._archive_path, "rb") as fptr:
            while True:
                buff = fptr.read(HASH_BUFFER_SIZE)
                if not buff:
                    break
                sha256.update(buff)
        return sha256.hexdigest()

    def get_archive_type(self) -> ArtifactArchiveType:
        """
        Returns the type of archive that was retrieved. This evaluation was determined by evaluating the file and not by
        the file name.

        :raises FetchRequiredError: If `fetch()` has not been successfully invoked.
        """
        self._fetch_guard("Archive has not been downloaded, so the type can't be determined.")

        return self._archive_type
