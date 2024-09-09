"""
:Description: TODO
"""

from __future__ import annotations

from enum import Enum, auto

class ArtifactSource(Enum):
    """
    TODO
    """
    GIT = auto()
    HTTP = auto()
    LOCAL = auto()

class ArtifactArchiveType(Enum):
    """
    TODO
    """
    ZIP = auto()
    # TODO determine how to do this in Python
    ZIP_7 = auto()  # 7zip
    TARBALL = auto()
    DIRECTORY = auto()  # Uncompressed artifact directory
