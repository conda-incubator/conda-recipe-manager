"""
:Description: Tests the `bump-recipe` CLI
"""

from typing import Final, cast
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands import bump_recipe
from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.fetcher.http_artifact_fetcher import HttpArtifactFetcher
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from tests.file_loading import get_test_path, load_recipe
from tests.http_mocking import MockHttpStreamResponse
from tests.smoke_testing import assert_cli_usage


class MockUrl:
    """
    Namespace for mocked URLs
    """

    # URL endpoint(s) used by the `types-toml.yaml` file
    TYPES_TOML_V0_10_8_20240310_URL: Final[str] = (
        "https://pypi.io/packages/source/t/types-toml/types-toml-0.10.8.20240310.tar.gz"
    )

    # Failed URL
    PYPI_HTTP_500: Final[str] = "https://pypi.io/error_500.html"


@pytest.fixture(name="http_fetcher_types_toml")
def fixture_http_fetcher_types_toml() -> HttpArtifactFetcher:
    """
    `HttpArtifactFetcher` test fixture for the `types-toml` project.
    """
    return HttpArtifactFetcher("types-toml", MockUrl.TYPES_TOML_V0_10_8_20240310_URL)


@pytest.fixture(name="http_pypi_failure")
def fixture_http_pypi_failure() -> HttpArtifactFetcher:
    """
    Single-instance `HttpArtifactFetcher` test fixture. This can be used for error cases that don't need multiple tests
    to be run or need to simulate a failed HTTP request.
    """
    return HttpArtifactFetcher("pypi_failure", MockUrl.PYPI_HTTP_500)


def mock_requests_get(*args: tuple[str], **_: dict[str, str | int]) -> MockHttpStreamResponse:
    """
    Mocking function for HTTP requests made in this test file.

    NOTE: The artifacts provided are not the real build artifacts.

    :param args: Arguments passed to the `requests.get()`
    :param _: Name-specified arguments passed to `requests.get()` (Unused)
    """
    endpoint = cast(str, args[0])
    match endpoint:
        case MockUrl.TYPES_TOML_V0_10_8_20240310_URL:
            return MockHttpStreamResponse(200, "archive_files/dummy_project_01.tar.gz")
        case MockUrl.PYPI_HTTP_500:
            return MockHttpStreamResponse(500, "archive_files/dummy_project_01.tar.gz")
        case _:
            # TODO fix: pyfakefs does include `/dev/null` by default, but this actually points to `<temp_dir>/dev/null`
            return MockHttpStreamResponse(404, "/dev/null")


def test_usage() -> None:
    """
    Smoke test that ensures rendering of the help menu
    """
    assert_cli_usage(bump_recipe.bump_recipe)


@pytest.mark.parametrize(
    "recipe_file,increment_build_num,expected_recipe_file",
    [
        ("types-toml.yaml", True, "bump_recipe/types-toml_build_num_1.yaml"),
        # TODO: Re-enable test when version bumping is supported.
        # ("types-toml.yaml", False, "bump_recipe/types-toml_version_bump.yaml"),
        # NOTE: These have no source section, therefore all SHA-256 update attempts (and associated network requests)
        # should be skipped.
        ("bump_recipe/build_num_1.yaml", True, "bump_recipe/build_num_2.yaml"),
        ("bump_recipe/build_num_1.yaml", False, "simple-recipe.yaml"),
        ("bump_recipe/build_num_42.yaml", True, "bump_recipe/build_num_43.yaml"),
        ("bump_recipe/build_num_42.yaml", False, "simple-recipe.yaml"),
        ("bump_recipe/build_num_-1.yaml", True, "simple-recipe.yaml"),
        ("bump_recipe/build_num_-1.yaml", False, "simple-recipe.yaml"),
    ],
)
def test_bump_recipe_cli(
    fs: FakeFilesystem,
    recipe_file: str,
    increment_build_num: bool,
    expected_recipe_file: str,
) -> None:
    """
    Test that the recipe file is successfully updated/bumped.

    :param fs: `pyfakefs` Fixture used to replace the file system
    :param request: Pytest fixture request object.
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / recipe_file
    expected_recipe_file_path = get_test_path() / expected_recipe_file

    cli_args: Final[list[str]] = (
        ["--build-num", str(recipe_file_path)] if increment_build_num else [str(recipe_file_path)]
    )

    with patch("requests.get", new=mock_requests_get):
        result = runner.invoke(bump_recipe.bump_recipe, cli_args)

    parser = load_recipe(recipe_file_path, RecipeParser)
    expected_parser = load_recipe(expected_recipe_file_path, RecipeParser)

    assert parser == expected_parser
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_cli_build_number_key_missing(fs: FakeFilesystem) -> None:
    """
    Test that a `build: number:` key is added and set to 0 when it's missing.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_num.yaml"
    expected_recipe_file_path = get_test_path() / "bump_recipe/build_num_added.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, [str(recipe_file_path)])

    parser = load_recipe(recipe_file_path, RecipeParser)
    expected_parser = load_recipe(expected_recipe_file_path, RecipeParser)

    assert parser == expected_parser
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_cli_build_number_not_int(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully case when the build number is not an integer,
    and we are trying to increment it.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/non_int_build_num.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_bump_cli_increment_build_num_key_not_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully when the build number key is missing and we try to increment it's value.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_num.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_bump_cli_no_build_key_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully when the build key is missing and we try to revert build number to zero.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / "bump_recipe/no_build_key.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, [str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION
