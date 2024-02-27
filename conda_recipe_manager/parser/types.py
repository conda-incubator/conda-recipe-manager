"""
File:           types.py
Description:    Provides public types, type aliases, constants, and small classes used by the parser.
"""
from __future__ import annotations

from enum import StrEnum, auto
from typing import Final

from percy.types import Primitives, SchemaType

#### Types ####

# Nodes can store a single value or a list of strings (for multiline-string nodes)
NodeValue = Primitives | list[str]


#### Constants ####

# The "new" recipe format introduces the concept of a schema version. Presumably the "old" recipe format would be
# considered "0". When converting to the new format, we'll use this constant value.
CURRENT_RECIPE_SCHEMA_FORMAT: Final[int] = 1

# Indicates how many spaces are in a level of indentation
TAB_SPACE_COUNT: Final[int] = 2
TAB_AS_SPACES: Final[str] = " " * TAB_SPACE_COUNT

# Schema validator for JSON patching
JSON_PATCH_SCHEMA: Final[SchemaType] = {
    "type": "object",
    "properties": {
        "op": {"enum": ["add", "remove", "replace", "move", "copy", "test"]},
        "path": {"type": "string", "minLength": 1},
        "from": {"type": "string"},
        "value": {
            "type": [
                "string",
                "number",
                "object",
                "array",
                "boolean",
                "null",
            ],
            "items": {
                "type": [
                    "string",
                    "number",
                    "object",
                    "array",
                    "boolean",
                    "null",
                ]
            },
        },
    },
    "required": [
        "op",
        "path",
    ],
    "allOf": [
        # `value` is required for `add`/`replace`/`test`
        {
            "if": {
                "properties": {"op": {"const": "add"}},
            },
            "then": {"required": ["value"]},
        },
        {
            "if": {
                "properties": {"op": {"const": "replace"}},
            },
            "then": {"required": ["value"]},
        },
        {
            "if": {
                "properties": {"op": {"const": "test"}},
            },
            "then": {"required": ["value"]},
        },
        # `from` is required for `move`/`copy`
        {
            "if": {
                "properties": {"op": {"const": "move"}},
            },
            "then": {"required": ["from"]},
        },
        {
            "if": {
                "properties": {"op": {"const": "copy"}},
            },
            "then": {"required": ["from"]},
        },
    ],
    "additionalProperties": False,
}


class MultilineVariant(StrEnum):
    """
    Captures which "multiline" descriptor was used on a Node, if one was used at all.

    See this guide for details on the YAML spec:
      https://stackoverflow.com/questions/3790454/how-do-i-break-a-string-in-yaml-over-multiple-lines/21699210
    """

    NONE = ""
    PIPE = "|"
    PIPE_PLUS = "|+"
    PIPE_MINUS = "|-"
    CARROT = ">"
    CARROT_PLUS = ">+"
    CARROT_MINUS = ">-"


class MessageCategory(StrEnum):
    """
    Categories to classify `RecipeParser` messages into.
    """

    ERROR = auto()
    WARNING = auto()


class MessageTable:
    """
    Stores and tags messages that may come up during `RecipeParser` operations. It is up to the client program to
    handle the logging of these messages.
    """

    def __init__(self) -> None:
        """
        Constructs an empty message table
        """
        self._tbl: dict[MessageCategory, list[str]] = {}

    def add_message(self, category: MessageCategory, message: str) -> None:
        """
        Adds a message to the table
        :param category:
        :param message:
        """
        if category not in self._tbl:
            self._tbl[category] = []
        self._tbl[category].append(message)

    def get_messages(self, category: MessageCategory) -> list[str]:
        """
        Returns all the messages stored in a given category
        :param category: Category to target
        :returns: A list containing all the messages stored in a category.
        """
        if category not in self._tbl:
            return []
        return self._tbl[category]

    def get_message_count(self, category: MessageCategory) -> int:
        """
        Returns how many messages are stored in a given category
        :param category: Category to target
        :returns: A list containing all the messages stored in a category.
        """
        if category not in self._tbl:
            return 0
        return len(self._tbl[category])

    def get_totals_message(self) -> str:
        """
        Convenience function that returns a displayable count of the number of warnings and errors contained in the
        messaging object.
        :returns: A message indicating the number of errors and warnings that have been accumulated. If there are none,
                  an empty string is returned.
        """
        if not self._tbl:
            return ""

        def _pluralize(n: int, s: str) -> str:
            if n == 1:
                return s
            return f"{s}s"

        num_errors: Final[int] = 0 if MessageCategory.ERROR not in self._tbl else len(self._tbl[MessageCategory.ERROR])
        errors: Final[str] = f"{num_errors} {_pluralize(num_errors, 'error')}"
        num_warnings: Final[int] = (
            0 if MessageCategory.WARNING not in self._tbl else len(self._tbl[MessageCategory.WARNING])
        )
        warnings: Final[str] = f"{num_warnings} {_pluralize(num_warnings, 'warning')}"

        return f"{errors} and {warnings} were found."
