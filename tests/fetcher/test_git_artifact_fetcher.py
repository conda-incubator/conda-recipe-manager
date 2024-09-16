"""
:Description: Unit tests for the `GitArtifactFetcher` class. NOTE: All tests in this file should use `pyfakefs` to
    prevent writing to disk.
"""

from __future__ import annotations

# NOTE: This test uses mocked git repos stored as tarballs. This comment tracks information about what is contained in
# those test repositories.
#
# dummy_git_project_01.tar.gz
#   - Tag `v1.0` and Ref `7ce5639724381d819835c0bfb171d855a2ca9c44`: First commit, contains README.md and homer.py
#   - Tag `v1.1` and Ref `1658a7b9e71d5ed027b4f1e27913e929a1c9755a`: Second commit, Adds marge.py
#   - Branch `eat_my_shorts`: Adds bart.py (based on `v1.0`)
