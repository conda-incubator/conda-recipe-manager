"""
File:           convert.py
Description:    CLI for converting an old recipe file to the "new" format.
"""
from __future__ import annotations

import os
import sys
from enum import IntEnum
from typing import Final

import click

from percy.parser.recipe_parser import RecipeParser
from percy.parser.types import MessageCategory, MessageTable

# Required file name for the recipe, specified in CEP-13
NEW_FORMAT_RECIPE_FILE_NAME: Final[str] = "recipe.yaml"


class ExitCode(IntEnum):
    """
    Error codes
    """

    SUCCESS = 0
    CLICK_ERROR = 1  # Controlled by the `click` library
    CLICK_USAGE = 2  # Controlled by the `click` library
    # Errors are roughly ordered by increasing severity
    RENDER_WARNINGS = 100
    RENDER_ERRORS = 101
    PARSE_EXCEPTION = 102
    RENDER_EXCEPTION = 103


def print_out(*args, **kwargs):
    """
    Convenience wrapper that prints to STDOUT
    """
    print(*args, file=sys.stdout, **kwargs)


def print_err(*args, **kwargs):
    """
    Convenience wrapper that prints to STDERR
    """
    print(*args, file=sys.stderr, **kwargs)


def print_messages(category: MessageCategory, msg_tbl: MessageTable):
    """
    Convenience function for dumping a series of messages of a certain category
    :param category: Category of messages to print
    :param msg_tbl: `MessageTable` instance containing the messages to print
    """
    msgs: Final[list[str]] = msg_tbl.get_messages(category)
    for msg in msgs:
        print_err(f"[{category.upper()}]: {msg}")


@click.command(short_help="Converts a `meta.yaml` formatted-recipe file to the new `recipe.yaml` format")
@click.argument("file", type=click.File("r", encoding="utf-8"))
@click.option("--output", "-o", type=click.Path(exists=False), default=None, help="File to dump a new recipe to.")
def convert(file: click.File, output: click.Path) -> None:  # pylint: disable=redefined-outer-name
    """
    Recipe conversion CLI utility. By default, recipes print to STDOUT. Messages always print to STDERR.
    """
    recipe_content: Final[str] = file.read()

    parser: RecipeParser
    try:
        parser = RecipeParser(recipe_content)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print_err("An exception occurred while parsing the recipe file:")
        print_err(e)
        sys.exit(ExitCode.PARSE_EXCEPTION)

    result: str
    msg_tbl: MessageTable
    try:
        result, msg_tbl = parser.render_to_new_recipe_format()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print_err("An exception occurred while converting to the new recipe file:")
        print_err(e)
        sys.exit(ExitCode.RENDER_EXCEPTION)

    if output is None:
        print_out(result)
    else:
        if not os.path.basename(output) == "recipe.yaml":
            print_err("WARNING: File is not called `recipe.yaml`.")
        with open(output, "w", encoding="utf-8") as fptr:
            fptr.write(result)

    error_count: Final[int] = msg_tbl.get_message_count(MessageCategory.ERROR)
    warn_count: Final[int] = msg_tbl.get_message_count(MessageCategory.WARNING)
    if (error_count + warn_count) > 0:
        print_messages(MessageCategory.WARNING, msg_tbl)
        print_messages(MessageCategory.ERROR, msg_tbl)
        print_err(msg_tbl.get_totals_message())
        if error_count > 0:
            sys.exit(ExitCode.RENDER_ERRORS)
        if warn_count > 0:
            sys.exit(ExitCode.RENDER_WARNINGS)

    sys.exit(ExitCode.SUCCESS)
