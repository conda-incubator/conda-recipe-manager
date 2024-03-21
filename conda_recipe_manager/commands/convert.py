"""
File:           convert.py
Description:    CLI for converting an old recipe file to the "new" format.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final, Optional

import click

from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.parser.types import MessageCategory, MessageTable

# Pre-CEP-13 name of the recipe file
OLD_FORMAT_RECIPE_FILE_NAME: Final[str] = "meta.yaml"
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
    READ_EXCEPTION = 104


@dataclass
class ConversionResult:
    """
    Struct that contains the results, metadata, errors, etc of converting a single recipe file.
    """

    code: ExitCode
    content: str
    file_path: Path
    msg_tbl: MessageTable


def print_out(*args, **kwargs) -> None:  # type: ignore
    """
    Convenience wrapper that prints to STDOUT
    """
    print(*args, file=sys.stdout, **kwargs)  # type: ignore


def print_err(*args, **kwargs) -> None:  # type: ignore
    """
    Convenience wrapper that prints to STDERR
    """
    print(*args, file=sys.stderr, **kwargs)  # type: ignore


def print_messages(category: MessageCategory, msg_tbl: MessageTable) -> None:
    """
    Convenience function for dumping a series of messages of a certain category
    :param category: Category of messages to print
    :param msg_tbl: `MessageTable` instance containing the messages to print
    """
    msgs: Final[list[str]] = msg_tbl.get_messages(category)
    for msg in msgs:
        print_err(f"[{category.upper()}]: {msg}")


def convert_file(file_path: Path, output: Optional[Path], print_output: bool) -> ConversionResult:
    """
    Converts a single recipe file to the new format, tracking results.
    :param file_path: Path to the recipe file to convert
    :param output: If specified, the file contents are written to this file path. Otherwise, the file is dumped to
        STDOUT IF `print_output` is set to `True`.
    :param print_output: Prints the recipe to STDOUT if the output file is not specified and this flag is `True`.
    :returns: A struct containing the results of the conversion process, including debugging metadata.
    """
    conversion_result = ConversionResult(code=ExitCode.SUCCESS, content="", file_path=file_path, msg_tbl=MessageTable())

    recipe_content = None
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            recipe_content = file.read()
    except IOError:
        pass

    if recipe_content is None:
        conversion_result.code = ExitCode.READ_EXCEPTION
        return conversion_result

    parser: RecipeParser
    try:
        parser = RecipeParser(recipe_content)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print_err("An exception occurred while parsing the recipe file:")
        print_err(e)
        conversion_result.code = ExitCode.PARSE_EXCEPTION
        return conversion_result

    try:
        conversion_result.content, conversion_result.msg_tbl = parser.render_to_new_recipe_format()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print_err("An exception occurred while converting to the new recipe file:")
        print_err(e)
        conversion_result.code = ExitCode.RENDER_EXCEPTION
        return conversion_result

    # Print or dump the results to a file. Printing is disabled for bulk operations.
    if output is None:
        if print_output:
            print_out(conversion_result.content)
    else:
        if not os.path.basename(output) == "recipe.yaml":
            print_err("WARNING: File is not called `recipe.yaml`.")
        with open(output, "w", encoding="utf-8") as fptr:
            fptr.write(conversion_result.content)

    error_count: Final[int] = conversion_result.msg_tbl.get_message_count(MessageCategory.ERROR)
    warn_count: Final[int] = conversion_result.msg_tbl.get_message_count(MessageCategory.WARNING)
    if error_count > 0:
        conversion_result.code = ExitCode.RENDER_ERRORS
    elif warn_count > 0:
        conversion_result.code = ExitCode.RENDER_WARNINGS
    return conversion_result


def process_recipe(file: Path, path: Path, output: Optional[Path]) -> tuple[str, ConversionResult]:
    """
    Helper function that performs the conversion operation for parallelizable execution.
    :param file: Recipe file to convert
    :param path: Path argument provided by the user
    :param output: Output argument file provided by the user
    :returns: Tuple containing the key/value pairing that tracks the result of the conversion operation
    """
    out_file: Optional[Path] = None if output is None else file.parent / output
    project_name = file.relative_to(path).parts[0]
    return project_name, convert_file(file, out_file, False)


@click.command(short_help="Converts a `meta.yaml` formatted-recipe file to the new `recipe.yaml` format.")
@click.argument("path", type=click.Path(exists=True, path_type=Path))  # type: ignore[misc]
@click.option(
    "--output",
    "-o",
    type=click.Path(exists=False),
    default=None,
    help=(
        "File to dump a new recipe to."
        f" For bulk operations, specify the file basename only (i.e. {NEW_FORMAT_RECIPE_FILE_NAME})."
    ),
)
def convert(path: Path, output: Optional[Path]) -> None:  # pylint: disable=redefined-outer-name
    """
    Recipe conversion CLI utility. By default, recipes print to STDOUT. Messages always print to STDERR. Takes 1 file or
    a directory containing multiple feedstock repositories. If the `PATH` provided is a directory, the script will
    attempt a bulk operation conversion across all subdirectories.
    """
    start_time: Final[float] = time.time()
    files: list[Path] = []
    results: dict[str, ConversionResult] = {}

    # Establish which mode of operation we are in, based on the path passed-in
    if path.is_dir():
        for file_path in path.rglob(OLD_FORMAT_RECIPE_FILE_NAME):
            files.append(file_path)
        if not files:
            print_err("Could not find any recipe files in this directory.")
            sys.exit(ExitCode.CLICK_USAGE)
    elif path.is_file():
        files.append(path)
    else:
        print_err("Could not identify path as file or directory.")
        sys.exit(ExitCode.CLICK_USAGE)

    ## Single-file case ##
    if len(files) == 1:
        result: Final[ConversionResult] = convert_file(files[0], output, True)
        print_messages(MessageCategory.WARNING, result.msg_tbl)
        print_messages(MessageCategory.ERROR, result.msg_tbl)
        print_err(result.msg_tbl.get_totals_message())
        sys.exit(result.code)

    ## Bulk operation ##

    # Process recipes in parallel
    thread_pool_size: Final[int] = mp.cpu_count()
    with mp.Pool(thread_pool_size) as pool:
        results = dict(pool.starmap(process_recipe, [(file, path, output) for file in files]))  # type: ignore[misc]

    # Tracking failures from bulk operation
    recipes_with_except: list[str] = []
    recipes_with_errors: list[str] = []
    recipes_with_warnings: list[str] = []
    errors_histogram: dict[str, int] = {}
    warnings_histogram: dict[str, int] = {}
    # Stats from bulk operation
    total_time: Final[float] = time.time() - start_time
    total_recipes: Final[int] = len(files)
    # Total count of errors/warnings
    total_errors: int = 0
    total_warnings: int = 0
    # Count of recipes with at least 1 exception/error/warning
    num_recipe_success: int = 0

    for project_name, result in results.items():
        if result.code in {ExitCode.PARSE_EXCEPTION, ExitCode.READ_EXCEPTION, ExitCode.RENDER_EXCEPTION}:
            recipes_with_except.append(project_name)

        errors = result.msg_tbl.get_messages(MessageCategory.ERROR)
        warnings = result.msg_tbl.get_messages(MessageCategory.WARNING)

        ## Errors ##
        for error in errors:
            if error not in errors_histogram:
                errors_histogram[error] = 0
            errors_histogram[error] += 1
        total_errors += len(errors)
        if errors:
            recipes_with_errors.append(project_name)

        ## Warnings ##
        for warning in warnings:
            if warning not in warnings_histogram:
                warnings_histogram[warning] = 0
            warnings_histogram[warning] += 1
        total_warnings += len(warnings)
        if warnings:
            recipes_with_warnings.append(project_name)

        ## Success ##
        if result.code in {ExitCode.SUCCESS, ExitCode.RENDER_WARNINGS} and not errors:
            num_recipe_success += 1

    stats = {
        "total_recipe_files": total_recipes,
        "total_recipes_processed": len(results),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "num_recipe_exceptions": len(recipes_with_except),
        "num_recipe_errors": len(recipes_with_errors),
        "num_recipe_warnings": len(recipes_with_warnings),
        "num_recipe_success": num_recipe_success,
        "percent_recipe_exceptions": round(len(recipes_with_except) / total_recipes, 2),
        "percent_recipe_errors": round(len(recipes_with_errors) / total_recipes, 2),
        "percent_recipe_warnings": round(len(recipes_with_warnings) / total_recipes, 2),
        "percent_recipe_success": round(num_recipe_success / total_recipes, 2),
        "timings": {
            "total_exec_time": round(total_time, 2),
            "avg_recipe_time": round(total_time / total_recipes, 2),
            "thread_pool_size": thread_pool_size,
        },
    }

    final_output = {
        "recipes_with_exceptions": recipes_with_except,
        "recipes_with_errors": recipes_with_errors,
        "recipes_with_warnings": recipes_with_warnings,
        "error_histogram": errors_histogram,
        "warnings_histogram": warnings_histogram,
        "statistics": stats,
    }

    print_out(json.dumps(final_output, indent=2))
    sys.exit(ExitCode.SUCCESS)
