"""
:Description: Parser that is capable of comprehending Conda Build Configuration (CBC) files.
"""

from __future__ import annotations

from typing import Final, Optional

from conda_recipe_manager.parser.recipe_parser import RecipeParser

class CBCParser(RecipeParser):
    """
    This work is based off of the `RecipeParser` class. The CBC file format happens to be similar enough to
    the recipe format (with commented selectors)

    TODO: Find out what/if there is an equivalent in the V1 recipe format.
    """

    def __init__(self, content: str):
        """
        TODO

        :param content: conda-build formatted recipe file, as a single text string.
        """
        super().__init__(content)
        self._cbc_vars_tbl = {}

    # TODO override irrelevant functions/refactor the parser core into its own parent class? Maybe a separate the
    # READ ONLY portion?
