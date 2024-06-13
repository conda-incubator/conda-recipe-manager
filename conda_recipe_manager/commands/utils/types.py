"""
File:           types.py
Description:    Contains types and constants used by CLI commands.
"""

from __future__ import annotations

from typing import Final

# Pre-CEP-13 name of the recipe file
V0_FORMAT_RECIPE_FILE_NAME: Final[str] = "meta.yaml"
# Required file name for the recipe, specified in CEP-13
V1_FORMAT_RECIPE_FILE_NAME: Final[str] = "recipe.yaml"
