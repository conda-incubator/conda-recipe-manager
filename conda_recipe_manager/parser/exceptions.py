"""
:Description: Provides exceptions thrown by the parser.
"""

from __future__ import annotations

import json

from conda_recipe_manager.types import JsonPatchType


class JsonPatchValidationException(Exception):
    """
    Indicates that the calling code has attempted to use an illegal JSON patch payload that does not meet the schema
    criteria.
    """

    def __init__(self, patch: JsonPatchType):
        """
        Constructs a JSON Patch Validation Exception

        :param op: Operation being encountered.
        """
        super().__init__(f"Invalid patch was attempted:\n{json.dumps(patch, indent=2)}")
