from typing import NamedTuple, Optional

from conda_recipe_manager.parser.platform_types import Arch, OperatingSystem, Platform


class SelectorQuery(NamedTuple):
    """
    TODO
    """

    arch: Optional[Arch] = None
    os: Optional[OperatingSystem] = None
    platform: Optional[Platform] = None
