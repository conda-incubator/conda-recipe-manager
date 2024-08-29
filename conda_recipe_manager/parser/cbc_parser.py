"""
:Description: Parser that is capable of comprehending Conda Build Configuration (CBC) files.
"""

from __future__ import annotations

from typing import Final, NamedTuple, Optional, cast

from conda_recipe_manager.parser.recipe_parser import RecipeParser
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

# Internal variable table
_CBCTable = dict[str, list[_CBCEntry]]


# TODO RecipeReader
class CBCParser(RecipeParser):
    """
    Parses a Conda Build Configuration (CBC) file and provides querying capabilities. Often these files are named
    `conda_build_configuration.yaml` or `cbc.yaml`

    This work is based off of the `RecipeParser` class. The CBC file format happens to be similar enough to
    the recipe format (with commented selectors)
    """
    # TODO: Find out what/if there is an equivalent in the V1 recipe format.

    def __init__(self, content: str):
        """
        Constructs a CBC Parser instance from the contents of a CBC file.

        :param content: conda-build formatted configuration file, as a single text string.
        """
        super().__init__(content)
        self._cbc_vars_tbl: _CBCTable = {}

        # TODO Handle special cases:
        #   - pin_run_as_build
        #   - zip_keys
        #     - python (versions)
        #     - numpy
        #     - The CBC file matches the python version and numpy version by list index
        #   - r_implementation
        # From Charles: "Compared to meta.yaml, no jinja is allowed in the cbc. Also I believe only the base subset of
        #                selectors is available (so py>=38 and py<=310 wouldn't work). To be confirmed though."

        parsed_contents: Final[dict[str, list[Primitives]]] = cast(dict[str, list[Primitives]], self.get_value("/"))
        for variable, value_list in parsed_contents.items():
            if not isinstance(value, list):
                continue

            for i, value in enumerate(value_list):
                path = RecipeParser.append_to_path(f"/{variable}/{i}")
                # TODO add V1 support for CBC files? Is there a V1 CBC format?
                entry = _CBCEntry(
                    value=value,
                    selector=SelectorParser(self.get_selector_at_path(path, None), SchemaVersion.V0),
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
        # TODO filter-out zip-keys and other special cases
        return list(self._cbc_vars_tbl.keys())

    def get_cbc_variable_value(self, variable: str, query: SelectorQuery, default: Primitives | SentinelType = RecipeParser._sentinel) -> Primitives:
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
            if default == RecipeParser._sentinel:
                raise KeyError(f"CBC variable not found: {variable}")
            return default

        cbc_entries: Final[list[_CBCEntry]] = self._cbc_vars_tbl[variable]
        if len(cbc_entries) == 0 and cbc_entries[0].selector is None:
            return variable

        for entry in cbc_entries:
            if entry.selector is None or entry.selector.does_selector_apply(query):
                return entry.value

        # No applicable entries have been found to match any selector variant.
        if default == RecipeParser._sentinel:
            raise ValueError(f"CBC variable does not have a value for the provided selector query: {variable}")
        return default
