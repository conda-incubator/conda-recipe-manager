"""
File:           _types.py
Description:    Provides private types, type aliases, constants, and small classes used by the parser and related files.
"""

from __future__ import annotations

import re
from typing import Final

import yaml

#### Private Types (Not to be used external to the `parser` module) ####

# Type alias for a list of strings treated as a Pythonic stack
StrStack = list[str]
# Type alias for a `StrStack` that must be immutable. Useful for some recursive operations.
StrStackImmutable = tuple[str, ...]

#### Private Constants (Not to be used external to the `parser` module) ####

# String that represents a root node in our path.
ROOT_NODE_VALUE: Final[str] = "/"
# Marker used to temporarily work around some Jinja-template parsing issues
RECIPE_MANAGER_SUB_MARKER: Final[str] = "__RECIPE_MANAGER_SUBSTITUTION_MARKER__"

# Ideal sort-order of the top-level YAML keys for human readability and traditionally how we organize our files. This
# should work on both old and new recipe formats.
TOP_LEVEL_KEY_SORT_ORDER: Final[dict[str, int]] = {
    "schema_version": 0,
    "context": 10,
    "package": 20,
    "recipe": 30,  # Used in the v1 recipe format
    "source": 40,
    "files": 50,
    "build": 60,
    "requirements": 70,
    "outputs": 80,
    "test": 90,
    "tests": 100,  # Used in the v1 recipe format
    "about": 110,
    "extra": 120,
}

# Canonical sort order for the new "v1" recipe format's `build` block
V1_SOURCE_SECTION_KEY_SORT_ORDER: Final[dict[str, int]] = {
    # URL source fields
    "url": 0,
    "sha256": 10,
    "md5": 20,
    # Local source fields (not including above)
    "path": 30,
    "use_gitignore": 40,
    # Git source fields (not including above)
    "git": 50,
    "branch": 60,
    "tag": 70,
    "rev": 80,
    "depth": 90,
    "lfs": 100,
    # Common fields
    "target_directory": 120,
    "file_name": 130,
    "patches": 140,
}

# Canonical sort order for the new "v1" recipe format's `build` block
V1_BUILD_SECTION_KEY_SORT_ORDER: Final[dict[str, int]] = {
    "number": 0,
    "string": 10,
    "skip": 20,
    "noarch": 30,
    "script": 40,
    "merge_build_and_host_envs": 50,
    "always_include_files": 60,
    "always_copy_files": 70,
    "variant": 80,
    "python": 90,
    "prefix_detection": 100,
    "dynamic_linking": 110,
}

# Canonical sort order for the new "v1" recipe format's `tests` block
V1_TEST_SECTION_KEY_SORT_ORDER: Final[dict[str, int]] = {
    "script": 0,
    "requirements": 10,
    "files": 20,
    "python": 30,
    "downstream": 40,
}

#### Private Classes (Not to be used external to the `parser` module) ####

# NOTE: The classes put in this file should be structures (NamedTuples) and very small support classes that don't make
# sense to dedicate a file for.


class ForceIndentDumper(yaml.Dumper):
    """
    Custom YAML dumper used to include optional indentation for human readability.
    Adapted from: https://stackoverflow.com/questions/25108581/python-yaml-dump-bad-indentation
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # pylint: disable=unused-argument
        return super().increase_indent(flow, False)


class Regex:
    """
    Namespace used to organize all regular expressions used by the `parser` module.
    """

    # Pattern to detect Jinja variable names and functions
    _JINJA_VAR_FUNCTION_PATTERN: Final[str] = r"[a-zA-Z_][a-zA-Z0-9_\|\'\"\(\)\, =\.\-]*"

    ## Pre-process conversion tooling regular expressions ##
    # Finds `environ[]` used by a some recipe files. Requires a whitespace character to prevent matches with
    # `os.environ[]`, which is very rare.
    PRE_PROCESS_ENVIRON: Final[re.Pattern[str]] = re.compile(r"\s+environ\[(\"|')(.*)(\"|')\]")

    ## Jinja regular expressions ##
    JINJA_SUB: Final[re.Pattern[str]] = re.compile(r"{{\s*" + _JINJA_VAR_FUNCTION_PATTERN + r"\s*}}")
    JINJA_FUNCTION_LOWER: Final[re.Pattern[str]] = re.compile(r"\|\s*lower")
    JINJA_LINE: Final[re.Pattern[str]] = re.compile(r"({%.*%}|{#.*#})\n")
    JINJA_SET_LINE: Final[re.Pattern[str]] = re.compile(r"{%\s*set\s*" + _JINJA_VAR_FUNCTION_PATTERN + r"\s*=.*%}\s*\n")

    SELECTOR: Final[re.Pattern[str]] = re.compile(r"\[.*\]")
    # Detects the 6 common variants (3 |'s, 3 >'s). See this guide for more info:
    #   https://stackoverflow.com/questions/3790454/how-do-i-break-a-string-in-yaml-over-multiple-lines/21699210
    MULTILINE: Final[re.Pattern[str]] = re.compile(r"^\s*.*:\s+(\||>)(\+|\-)?(\s*|\s+#.*)")
    # Group where the "variant" string is identified
    MULTILINE_VARIANT_CAPTURE_GROUP_CHAR: Final[int] = 1
    MULTILINE_VARIANT_CAPTURE_GROUP_SUFFIX: Final[int] = 2
    DETECT_TRAILING_COMMENT: Final[re.Pattern[str]] = re.compile(r"(\s)+(#)")
