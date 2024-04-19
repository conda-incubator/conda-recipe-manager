#!/usr/bin/env python3
"""
File:           parse_ci_output.py
Description:    Given a directory of CI logs, parse and organize the JSON output for easier consumption.
                This is a quick and dirty script, not meant to be maintained with the usual standard of quality.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Final, cast, no_type_check

# Adapted from: https://stackoverflow.com/questions/3143070/regex-to-match-an-iso-8601-datetime-string
ISO_8601_REGEX: Final[re.Pattern[str]] = re.compile(r"\d{4}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d\.\d+Z\s")

# Regex used to find a single JSON blob
JSON_OBJ_REGEX: Final[re.Pattern[str]] = re.compile(r"\n\{\n.*\n\}\n", re.MULTILINE | re.DOTALL)

# Basic JSON type to shut the static analyzer up for our purposes. Allows the script to be run independently without
# referencing the better JSON type defined in this project.
BasicJsonType = dict[str, dict[str, int | str] | str]


@no_type_check
def generate_summary(convert_results: list[BasicJsonType], dry_run_results: list[BasicJsonType]) -> BasicJsonType:
    """
    Given the list of parsed JSON blobs of interest from the log files, summarize the results.

    NOTE: Type-checking has been disabled for this function given that the statistics we will track may change
    frequently and we don't want this helper script to become a maintenance headache. The access of JSON values is on
    output that we have direct control over.

    :param convert_results: List of parsed JSON for conversion results
    :param dry_run_results: List of parsed JSON for dry-run results
    :returns: Summary JSON object to display in the final results.
    """
    test_counts: dict[str, int] = {}

    # Aggregate conversion stats
    for result in convert_results:
        test = Path(result["info"]["directory"]).name
        test_counts.setdefault(test, 0)
        test_counts[test] += 1

    # Aggregate dry-run stats
    for result in dry_run_results:
        test = Path(result["info"]["directory"]).name
        test_counts.setdefault(test, 0)
        test_counts[test] += 1

    return {
        "test_counts": dict(sorted(test_counts.items())),
        "stages": {
            "recipe_conversion": {},
            "rattler_dry_run": {},
        },
    }


def main() -> None:
    """
    Main execution point of the script
    """
    parser = argparse.ArgumentParser(
        description="Extracts JSON results from CI operations from a directory of CI log files"
    )
    parser.add_argument("dir", type=Path, help="Directory that contains log files to parse.")  # type: ignore[misc]
    args = parser.parse_args()

    log_dir: Final[Path] = Path(cast(str, args.dir))

    # Separate test results into their own lists
    convert_results: list[BasicJsonType] = []
    dry_run_results: list[BasicJsonType] = []

    # Parse-out all the recognized JSON blobs found in the log files.
    for file in log_dir.iterdir():
        if file.is_dir() or file.name == ".DS_Store":
            continue
        content = file.read_text(encoding="utf-8")
        # Strip out all the timestamps
        lines = ISO_8601_REGEX.sub("", content).splitlines()

        start_idx = 0
        for i, line in enumerate(lines):
            if line == "{":
                start_idx = i
            if line == "}":
                # Log the range of lines that failed to be recognized, if need be.
                log_range = f"{file}:{start_idx+1}-{i+1}"
                try:
                    data = cast(BasicJsonType, json.loads("\n".join(lines[start_idx : i + 1])))
                    # Filter-out unrecognized JSON blobs in the logs
                    if "info" not in data or "command_name" not in data["info"]:
                        print(f"Could not recognize JSON object from {log_range}", file=sys.stderr)
                        continue
                    if data["info"]["command_name"] == "convert":  # type: ignore[index]
                        convert_results.append(data)
                    else:
                        dry_run_results.append(data)
                except json.JSONDecodeError:
                    start_idx = 0
                    print(f"Could not parse lines from {log_range}", file=sys.stderr)
                    continue

    # Aggregate the final results, putting the summary information at the top, followed by the raw results from the
    # log files.
    final_results = {
        "summary": cast(BasicJsonType, generate_summary(convert_results, dry_run_results)),
        # TODO re-enable
        # "raw_conversion_results": convert_results,
        # "raw_dry_run_results": dry_run_results,
    }

    print(json.dumps(final_results, indent=2))


if __name__ == "__main__":
    main()
