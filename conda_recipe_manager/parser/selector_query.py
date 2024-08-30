from typing import NamedTuple, Optional

from conda_recipe_manager.parser.platform_types import Arch, OperatingSystem, Platform


class SelectorQuery(NamedTuple):
    """
    TODO
    """

    platform: Optional[Platform] = None
