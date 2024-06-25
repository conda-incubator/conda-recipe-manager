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
# should work on both V0 (pre CEP-13) and V1 recipe formats.
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

# Canonical sort order for the V1 Python test element
V1_PYTHON_TEST_KEY_SORT_ORDER: Final[dict[str, int]] = {
    "imports": 0,
    "pip_check": 10,
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
    # Finds commonly used variants of `{{ hash_type }}:` which is a substitution for the `sha256` field
    PRE_PROCESS_JINJA_HASH_TYPE_KEY: Final[re.Pattern[str]] = re.compile(
        r"'{0,1}\{\{ (hash_type|hash|hashtype) \}\}'{0,1}:"
    )
    # Finds set statements that use dot functions over piped functions (`foo.replace(...)` vs `foo | replace(...)`).
    # Group 1 and Group 2 match the left and right sides of the period mark.
    PRE_PROCESS_JINJA_DOT_FUNCTION_IN_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(
        r"(\{%\s*set.*=.*)\.(.*\(.*\)\s*%\})"
    )
    PRE_PROCESS_JINJA_DOT_FUNCTION_IN_SUBSTITUTION: Final[re.Pattern[str]] = re.compile(
        r"(\{\{\s*[a-zA-Z0-9_]*.*)\.([a-zA-Z0-9_]*\(.*\)\s*\}\})"
    )
    # Strips empty parenthesis artifacts on functions like `| lower`
    PRE_PROCESS_JINJA_DOT_FUNCTION_STRIP_EMPTY_PARENTHESIS: Final[re.Pattern[str]] = re.compile(
        r"(\|\s*(lower|upper))(\(\))"
    )
    # Attempts to normalize multiline strings containing quoted escaped newlines.
    PRE_PROCESS_QUOTED_MULTILINE_STRINGS: Final[re.Pattern[str]] = re.compile(r"(\s*)(.*):\s*['\"](.*)\\n(.*)['\"]")
    # rattler-build@0.18.0 deprecates `min_pin` and `max_pin`
    PRE_PROCESS_MIN_PIN_REPLACEMENT: Final[re.Pattern[str]] = re.compile(r"min_pin=")
    PRE_PROCESS_MAX_PIN_REPLACEMENT: Final[re.Pattern[str]] = re.compile(r"max_pin=")

    ## Jinja regular expressions ##
    JINJA_SUB: Final[re.Pattern[str]] = re.compile(r"{{\s*" + _JINJA_VAR_FUNCTION_PATTERN + r"\s*}}")
    JINJA_LINE: Final[re.Pattern[str]] = re.compile(r"({%.*%}|{#.*#})\n")
    JINJA_SET_LINE: Final[re.Pattern[str]] = re.compile(r"{%\s*set\s*" + _JINJA_VAR_FUNCTION_PATTERN + r"\s*=.*%}\s*\n")
    # Useful for replacing the older `{{` JINJA substitution with the newer `${{` WITHOUT accidentally doubling-up the
    # newer syntax when multiple replacements are possible.
    JINJA_REPLACE_V0_STARTING_MARKER: Final[re.Pattern[str]] = re.compile(r"(?<!\$)\{\{")

    # All recognized JINJA functions are kept in a set for the convenience of trying to match against all of them.
    # Group 1 contains the function name, Group 2 contains the arguments, if any.
    JINJA_FUNCTION_LOWER: Final[re.Pattern[str]] = re.compile(r"\|\s*(lower)")
    JINJA_FUNCTION_UPPER: Final[re.Pattern[str]] = re.compile(r"\|\s*(upper)")
    JINJA_FUNCTION_REPLACE: Final[re.Pattern[str]] = re.compile(r"\|\s*(replace)\((.*)\)")
    JINJA_FUNCTIONS_SET: Final[set[re.Pattern[str]]] = {
        JINJA_FUNCTION_LOWER,
        JINJA_FUNCTION_UPPER,
        JINJA_FUNCTION_REPLACE,
    }

    SELECTOR: Final[re.Pattern[str]] = re.compile(r"\[.*\]")
    # Detects the 6 common variants (3 |'s, 3 >'s). See this guide for more info:
    #   https://stackoverflow.com/questions/3790454/how-do-i-break-a-string-in-yaml-over-multiple-lines/21699210
    MULTILINE: Final[re.Pattern[str]] = re.compile(r"^\s*.*:\s+(\||>)(\+|\-)?(\s*|\s+#.*)")
    # Group where the "variant" string is identified
    MULTILINE_VARIANT_CAPTURE_GROUP_CHAR: Final[int] = 1
    MULTILINE_VARIANT_CAPTURE_GROUP_SUFFIX: Final[int] = 2
    DETECT_TRAILING_COMMENT: Final[re.Pattern[str]] = re.compile(r"(\s)+(#)")
