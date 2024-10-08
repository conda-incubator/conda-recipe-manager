#!/usr/bin/env python3
"""
:Description: TODO
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path
from typing import Final, Optional, cast

from conda_recipe_manager.parser.recipe_reader import RecipeReader
from conda_recipe_manager.parser.types import V0_FORMAT_RECIPE_FILE_NAME


def _process_recipe(file: Path) -> Optional[tuple[str, str]]:
    """


    :param file: Recipe file to examine
    :returns: TODO
    """
    try:
        parser = RecipeReader(file.read_text())

        # Filters out "Python packages"
        run_deps = cast(list[str], parser.get_value("/requirements/run", default=[], sub_vars=True))
        if "python" not in run_deps:
            return None

        pkg_name = cast(str, parser.get_value("/package/name", default="NO_PKG_NAME", sub_vars=True))
        # TODO fall-back mechanism
        # TODO remove `<name>.` edge case
        import_names = cast(str, parser.get_value("/test/imports", default="NO_IMPORT_NAME", sub_vars=True))
    except Exception:
        # TODO better error gathering
        return None

    # Sometimes the import name is not the first listed.
    for import_name in import_names:
        if pkg_name == import_name or import_name.startswith(f"{pkg_name}."):
            return None

    # TODO fuzzy-match the closest import name
    return (import_names[0], pkg_name)


def main() -> None:
    """
    Main execution point of the script
    """
    parser = argparse.ArgumentParser(description="TODO")
    # TODO validate path
    parser.add_argument("path", type=Path, help="Directory that contains recipe files.")  # type: ignore[misc]
    parser.add_argument("-i", "--ignore", action="append", type=Path, help="Directory to be ignored.")  # type: ignore[misc]
    args = parser.parse_args()

    recipe_path: Final[Path] = Path(cast(str, args.path))
    ignore_paths: Final[list[Path]] = [Path(cast(str, f)) for f in args.ignore]
    files = list(recipe_path.rglob(V0_FORMAT_RECIPE_FILE_NAME))

    # Ignore directories
    def _ignore_filter(file: Path) -> bool:
        for ignore in ignore_paths:
            if file.is_relative_to(ignore):
                return False
        return True

    thread_pool_size: Final[int] = mp.cpu_count()
    with mp.Pool(thread_pool_size) as pool:
        results = dict(filter(None, pool.map(_process_recipe, filter(_ignore_filter, files))))  # type: ignore[misc]

    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"Total count: {len(results)}")


if __name__ == "__main__":
    main()
