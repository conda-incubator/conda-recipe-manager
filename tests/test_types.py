"""
:Description: Unit tests for the types module
"""

from __future__ import annotations

from conda_recipe_manager.types import MessageCategory, MessageTable


def test_message_table_add_retrieve_and_clear() -> None:
    message_table = MessageTable()
    message_table.add_message(MessageCategory.ERROR, "Test error message")
    message_table.add_message(MessageCategory.WARNING, "Test warning message")

    assert message_table.get_totals_message() == "1 error and 1 warning were found."

    assert message_table.get_message_count(MessageCategory.EXCEPTION) == 0
    assert message_table.get_message_count(MessageCategory.ERROR) == 1
    assert message_table.get_message_count(MessageCategory.WARNING) == 1

    message_table.add_message(MessageCategory.ERROR, "Error message 2")

    assert message_table.get_message_count(MessageCategory.EXCEPTION) == 0
    assert message_table.get_message_count(MessageCategory.ERROR) == 2
    assert message_table.get_message_count(MessageCategory.WARNING) == 1

    assert message_table.get_totals_message() == "2 errors and 1 warning were found."

    message_table.clear_messages()
    assert message_table.get_message_count(MessageCategory.EXCEPTION) == 0
    assert message_table.get_message_count(MessageCategory.ERROR) == 0
    assert message_table.get_message_count(MessageCategory.WARNING) == 0
    assert message_table.get_totals_message() == ""
