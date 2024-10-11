"""
:Description: Unit tests for the types module
"""

from __future__ import annotations

import pytest

from conda_recipe_manager.types import MessageCategory, MessageTable


@pytest.mark.parametrize(
    "message,content,output",
    [
        (MessageCategory.WARNING, "Test warning message", "0 errors and 1 warning were found."),
        (MessageCategory.ERROR, "Test error message", "1 error and 0 warnings were found."),
    ],
)
def test_message_table_add(message: MessageCategory, content: str, output: str) -> None:
    """
    Tests the addition of messages to the message table and checks output of warnings and errors contained
    in the messaging object.

    param message: Message category
    param content: Message content
    param output: Expected output
    """
    message_table = MessageTable()
    message_table.add_message(message, content)
    assert message_table.get_totals_message() == output


@pytest.mark.parametrize(
    "message,content,count",
    [
        (MessageCategory.EXCEPTION, "Test exception message", 1),
        (MessageCategory.WARNING, "Test warning message", 1),
        (MessageCategory.ERROR, "Test error message", 1),
    ],
)
def test_message_get_count(message: MessageCategory, content: str, count: int) -> None:
    """
    Tests the addition of messages to the message table and checks the count of warnings and
    errors contained in the messaging object.

    param message: Message category
    param content: Message content
    param count: Expected count
    """
    message_table = MessageTable()

    message_table.add_message(message, content)
    assert message_table.get_message_count(message) == count


def test_message_table_clear() -> None:
    """
    Tests whether or not the message table properly clears all messages.
    """
    message_table = MessageTable()
    message_table.add_message(MessageCategory.ERROR, "Test warning message")
    message_table.add_message(MessageCategory.WARNING, "Test error message")

    message_table.clear_messages()
    assert message_table.get_message_count(MessageCategory.EXCEPTION) == 0
    assert message_table.get_message_count(MessageCategory.ERROR) == 0
    assert message_table.get_message_count(MessageCategory.WARNING) == 0
    assert message_table.get_totals_message() == ""
