"""
:Description: Generates a recipe graph from recipe files on local storage.
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Final, Optional

from conda_recipe_manager.grapher.recipe_graph import RecipeGraph
from conda_recipe_manager.parser.recipe_reader_deps import RecipeReaderDeps
from conda_recipe_manager.parser.types import V0_FORMAT_RECIPE_FILE_NAME, V1_FORMAT_RECIPE_FILE_NAME


class RecipeGraphFromDisk(RecipeGraph):
    """
    Constructs a Recipe Graph from disk/local storage.
    """

    @staticmethod
    def _read_and_parse_recipe(file: Path) -> tuple[str, Optional[RecipeReaderDeps]]:
        """
        Callback that parses a single recipe file.

        :param file: File to process
        :returns: A key-value pair to initialize the recipe cache. If parsing failed, this returns a tuple containing
            a debug string and None.
        """
        try:
            parser = RecipeReaderDeps(file.read_text())
            return (parser.calc_sha256(), parser)
        except Exception:  # pylint: disable=broad-exception-caught
            return (file.as_posix(), None)

    def __init__(self, directory: str | Path, cpu_count: int = 0):
        """
        Constructs common types that all recipe graphs share. Derived classes handle initialization details.

        :param directory: Path to the directory containing recipe files.
        :param cpu_count: (Optional) Overrides the number of CPUs to use when reading from disk.
        """
        self._dir_path = Path(directory)

        # TODO Handle the case where V0 and V1 recipes might exist in the same feedstock. Prefer V1?
        recipe_names: Final[set[str]] = {V0_FORMAT_RECIPE_FILE_NAME, V1_FORMAT_RECIPE_FILE_NAME}

        files = (f for f in self._dir_path.rglob("*.yaml") if f.name in recipe_names)

        # Process recipes in parallel
        thread_pool_size: Final[int] = mp.cpu_count() if cpu_count <= 0 else cpu_count
        with mp.Pool(thread_pool_size) as pool:
            results = pool.map(RecipeGraphFromDisk._read_and_parse_recipe, files)
        # Process results
        failed_paths: set[str] = set()
        recipe_cache: dict[str, RecipeReaderDeps] = {}
        for result in results:
            if result[1] is None:
                failed_paths.add(result[0])
                continue
            recipe_cache[result[0]] = result[1]

        super().__init__(recipe_cache, failed_paths)
