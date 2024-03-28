"""
File:           rattler_bulk_build.py
Description:    CLI tool that performs a bulk build operation for rattler-build.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final, cast

import click

from conda_recipe_manager.commands.utils.print import print_err

# Required file name for the recipe, specified in CEP-13
NEW_FORMAT_RECIPE_FILE_NAME: Final[str] = "recipe.yaml"
# When performing a bulk operation, overall "success" is indicated by the % of recipe files that were built
# "successfully"
DEFAULT_BULK_SUCCESS_PASS_THRESHOLD: Final[float] = 0.80
RATTLER_ERROR_REGEX = re.compile(r"Error:\s+.*")


class ExitCode(IntEnum):
    """
    Error codes to return upon script completion
    """

    SUCCESS = 0
    NO_FILES_FOUND = 1
    # In bulk operation mode, this indicates that the % success threshold was not met
    MISSED_SUCCESS_THRESHOLD = 42


@dataclass
class BuildResult:
    """
    Struct that contains the results, metadata, errors, etc of building a single recipe file.
    """

    code: ExitCode
    errors: list[str]


def build_recipe(file: Path, path: Path, args: list[str]) -> tuple[str, BuildResult]:
    """
    Helper function that performs the build operation for parallelizable execution. Logs rattler-build failures to
    STDERR.
    :param file: Recipe file to build
    :param path: Path argument provided by the user
    :param args: List of arguments to provide whole-sale to rattler-build
    :returns: Tuple containing the key/value pairing that tracks the result of the build operation
    """
    cmd: list[str] = ["rattler-build", "build", "-r", str(file)]
    cmd.extend(args)
    output: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        " ".join(cmd),
        encoding="utf-8",
        capture_output=True,
        shell=True,
        check=False,
    )

    return str(file.relative_to(path)), BuildResult(
        code=ExitCode(output.returncode),
        errors=cast(list[str], RATTLER_ERROR_REGEX.findall(output.stderr)),
    )


@click.command(
    short_help="Given a directory, performs a bulk rattler-build operation. Assumes rattler-build is installed.",
    context_settings=cast(
        dict[str, bool],
        {
            "ignore_unknown_options": True,
            "allow_extra_args": True,
        },
    ),
)
@click.argument("path", type=click.Path(exists=True, path_type=Path))  # type: ignore[misc]
@click.option(
    "--min-success-rate",
    "-m",
    type=click.FloatRange(0, 1),
    default=DEFAULT_BULK_SUCCESS_PASS_THRESHOLD,
    help="Sets a minimum passing success rate for bulk operations.",
)
@click.option(
    "--truncate",
    "-t",
    is_flag=True,
    help="Truncates logging. On large tests in a GitHub CI environment, this can eliminate log buffering issues.",
)
@click.pass_context
def rattler_bulk_build(ctx: click.Context, path: Path, min_success_rate: float, truncate: bool) -> None:
    """
    Given a directory of feedstock repositories, performs multiple recipe builds using rattler-build.
    All unknown options and arguments for this script are passed directly to `rattler-build build`.
    NOTE:
        - The build command is run as `rattler-build build -r <recipe.yaml> <ARGS>`
        - rattler-build errors are dumped to STDERR
    """
    start_time: Final[float] = time.time()
    files: Final[list[Path]] = []
    for file_path in path.rglob(NEW_FORMAT_RECIPE_FILE_NAME):
        files.append(file_path)

    if not files:
        print_err(f"No `recipe.yaml` files found in: {path}")
        sys.exit(ExitCode.NO_FILES_FOUND)

    # Process recipes in parallel
    thread_pool_size: Final[int] = mp.cpu_count()
    with mp.Pool(thread_pool_size) as pool:
        results = dict(pool.starmap(build_recipe, [(file, path, ctx.args) for file in files]))  # type: ignore[misc]

    # Gather statistics
    total_recipes: Final[int] = len(files)
    total_processed: Final[int] = len(results)
    total_errors = 0
    total_success = 0
    recipes_with_errors: list[str] = []
    error_histogram: dict[str, int] = {}
    for file, build_result in results.items():
        if build_result.code == ExitCode.SUCCESS:
            total_success += 1
        else:
            total_errors += 1
            recipes_with_errors.append(file)
        if build_result.errors:
            for error in build_result.errors:
                if error not in error_histogram:
                    error_histogram[error] = 0
                error_histogram[error] += 1
    percent_success: Final[float] = round(total_success / total_recipes, 2)

    total_time: Final[float] = time.time() - start_time
    stats = {
        "total_recipe_files": total_recipes,
        "total_recipes_processed": total_processed,
        "total_errors": total_errors,
        "percent_errors": round(total_errors / total_recipes, 2),
        "percent_success": percent_success,
        "timings": {
            "total_exec_time": round(total_time, 2),
            "avg_recipe_time": round(total_time / total_recipes, 2),
            "thread_pool_size": thread_pool_size,
        },
    }
    final_output = {
        "error_histogram": error_histogram,
        "stats": stats,
    }
    if not truncate:
        final_output["recipes_with_build_error_code"] = recipes_with_errors

    print(json.dumps(final_output, indent=2))
    sys.exit(ExitCode.SUCCESS if percent_success >= min_success_rate else ExitCode.MISSED_SUCCESS_THRESHOLD)
