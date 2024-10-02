"""
:Description: Parser that is capable of comprehending Conda Build Configuration (CBC) files.
"""

from __future__ import annotations

from typing import Final, NamedTuple, Optional, cast

from conda_recipe_manager.parser.recipe_reader import RecipeReader
from conda_recipe_manager.parser.selector_parser import SelectorParser
from conda_recipe_manager.parser.selector_query import SelectorQuery
from conda_recipe_manager.parser.types import SchemaVersion
from conda_recipe_manager.types import Primitives, SentinelType


class _CBCEntry(NamedTuple):
    """
    Internal representation of a variable's value in a CBC file.
    """

    value: Primitives
    selector: Optional[SelectorParser]


# Internal variable table type
_CbcTable = dict[str, list[_CBCEntry]]

# Type that attempts to represent the contents of a CBC file
_CbcType = dict[str, list[Primitives] | dict[str, dict[str, str]]]


class CbcParser(RecipeReader):
    """
    Parses a Conda Build Configuration (CBC) file and provides querying capabilities. Often these files are named
    `conda_build_configuration.yaml` or `cbc.yaml`

    This work is based off of the `RecipeReader` class. The CBC file format happens to be similar enough to
    the recipe format (with commented selectors)
    """

    # TODO: Add V1-support for the new CBC equivalent:
    #   https://prefix-dev.github.io/rattler-build/latest/variants/

    def __init__(self, content: str):
        """
        Constructs a CBC Parser instance from the contents of a CBC file.

        :param content: conda-build formatted configuration file, as a single text string.
        """
        super().__init__(content)
        self._cbc_vars_tbl: _CbcTable = {}

        # TODO Handle special cases:
        #   - pin_run_as_build
        #   - zip_keys
        #     - python (versions)
        #     - numpy
        #     - The CBC file matches the python version and numpy version by list index
        #   - r_implementation
        # From Charles: "Compared to meta.yaml, no jinja is allowed in the cbc. Also I believe only the base subset of
        #                selectors is available (so py>=38 and py<=310 wouldn't work). To be confirmed though."

        parsed_contents: Final[_CbcType] = cast(_CbcType, self.get_value("/"))
        for variable, value_list in parsed_contents.items():
            if not isinstance(value_list, list):
                continue

            # TODO track and calculate zip-key values
            if variable == "zip_keys":
                continue

            for i, value in enumerate(value_list):
                path = f"/{variable}/{i}"
                # TODO add V1 support for CBC files? Is there a V1 CBC format?
                selector = None
                try:
                    selector = SelectorParser(self.get_selector_at_path(path), SchemaVersion.V0)
                except KeyError:
                    pass
                entry = _CBCEntry(
                    value=value,
                    selector=selector,
                )
                # TODO detect duplicates
                if variable not in self._cbc_vars_tbl:
                    self._cbc_vars_tbl[variable] = [entry]
                else:
                    self._cbc_vars_tbl[variable].append(entry)

    def __contains__(self, key: object) -> bool:
        """
        Indicates if a variable is found in a CBC file.

        :param key: Target variable name to check for.
        :returns: True if the variable exists in this CBC file. False otherwise.
        """
        if not isinstance(key, str):
            return False
        return key in self._cbc_vars_tbl

    def list_cbc_variables(self) -> list[str]:
        """
        Get a list of all the available CBC variable names.

        :returns: A list containing all the variables defined in the CBC file.
        """
        return list(self._cbc_vars_tbl.keys())

    def get_cbc_variable_value(
        self, variable: str, query: SelectorQuery, default: Primitives | SentinelType = RecipeReader._sentinel
    ) -> Primitives:
        """
        Determines which value of a CBC variable is applicable to the current environment.

        :param variable: Target variable name.
        :param query: Query that represents the state of the target build environment.
        :param default: (Optional) Value to return if no variable could be found or no value could be determined.
        :raises KeyError: If the key does not exist and no default value is provided.
        :raises ValueError: If the selector query does not match any case and no default value is provided.
        :returns: Value of the variable as indicated by the selector options provided.
        """
        if variable not in self:
            if isinstance(default, SentinelType):
                raise KeyError(f"CBC variable not found: {variable}")
            return default

        cbc_entries: Final[list[_CBCEntry]] = self._cbc_vars_tbl[variable]

        # Short-circuit on trivial case: one value, no selector
        if len(cbc_entries) == 1 and cbc_entries[0].selector is None:
            return cbc_entries[0].value

        for entry in cbc_entries:
            if entry.selector is None or entry.selector.does_selector_apply(query):
                return entry.value

        # No applicable entries have been found to match any selector variant.
        if isinstance(default, SentinelType):
            raise ValueError(f"CBC variable does not have a value for the provided selector query: {variable}")
        return default
