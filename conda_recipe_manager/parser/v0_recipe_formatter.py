"""
:Description: The V0 Recipe Formatter attempts to improve parsing capabilities of V0 recipe files by formatting the file
    prior to parsing. The parser can be easily tripped up on bad indentation and some recipe files have been found to be
    incredibly malformed. Given the V0 format does not contain legal YAML, we cannot use a common YAML formatting tool,
    like `yamlfmt`. This tool is not perfect, but is meant to catch enough common formatting issues to increase CRM's
    parsing capabilities in the ecosystem.
"""

from __future__ import annotations

from typing import Final

from conda_recipe_manager.parser._utils import num_tab_spaces


class V0RecipeFormatter:
    """
    Class that attempts to format V0 recipe files in a way to improve parsing compatibility.
    """

    def __init__(self, content: str):
        """
        Constructs a `V0RecipeFormatter` instance.

        :param content: conda-build formatted recipe file, as a single text string.
        """
        self._lines = content.splitlines()

        # In order to be able to be invoked by the parser before parsing begins, we need to determine if the recipe file
        # Is V0 or not independently of the mechanism used by the parser.
        def _calc_is_v0_recipe() -> bool:
            # TODO improve
            return "schema_version:" not in content

        self._is_v0_recipe: Final[bool] = _calc_is_v0_recipe()

    def __str__(self) -> str:
        """
        Returns the text contained by this formatter instance.

        :returns: V0 recipe file contents as a single string.
        """
        return "\n".join(self._lines)

    def is_v0_recipe(self) -> bool:
        """
        Indicates if this file is formatted in the V0 recipe format.

        :returns: True if the recipe content provided is in the V0 format. False otherwise.
        """
        return self._is_v0_recipe

    def fmt_text(self) -> None:
        """
        Executes a number of custom V0 formatting rules in an attempt to improve the chances a V0 recipe can be parsed.
        """
        idx = 0
        num_lines: Final[int] = len(self._lines)
        while idx < num_lines:
            line = self._lines[idx]
            clean_line = line.strip()

            # Attempt to correct mis-matched comment indentations
            if clean_line and 0 < idx < num_lines - 1 and clean_line[0] == "#":
                prev_cntr = num_tab_spaces(self._lines[idx - 1])
                cur_cntr = num_tab_spaces(line)
                next_cntr = num_tab_spaces(self._lines[idx + 1])
                if prev_cntr == next_cntr and cur_cntr != next_cntr:
                    self._lines[idx] = (" " * next_cntr) + clean_line

            idx += 1
