"""
:Description: Tests the `bump-recipe` CLI
"""

from pathlib import Path
from typing import Final, Optional, cast
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from conda_recipe_manager.commands import bump_recipe
from conda_recipe_manager.commands.utils.types import ExitCode
from conda_recipe_manager.parser.recipe_reader import RecipeReader
from tests.file_loading import get_test_path, load_file, load_recipe
from tests.http_mocking import MockHttpStreamResponse
from tests.smoke_testing import assert_cli_usage


def mock_requests_get(*args: tuple[str], **_: dict[str, str | int]) -> MockHttpStreamResponse:
    """
    Mocking function for HTTP requests made in this test file.

    NOTE: The artifacts provided are not the real build artifacts.

    :param args: Arguments passed to the `requests.get()`
    :param _: Name-specified arguments passed to `requests.get()` (Unused)
    """
    endpoint = cast(str, args[0])
    default_artifact_set: Final[set[str]] = {
        # types-toml.yaml
        "https://pypi.io/packages/source/t/types-toml/types-toml-0.10.8.20240310.tar.gz",
        # boto.yaml
        "https://pypi.org/packages/source/b/boto/boto-2.50.0.tar.gz",
        # huggingface_hub.yaml
        "https://pypi.io/packages/source/h/huggingface_hub/huggingface_hub-0.24.6.tar.gz",
        # gsm-amzn2-aarch64.yaml
        "https://graviton-rpms.s3.amazonaws.com/amzn2-core_2021_01_26/amzn2-core/gsm-1.0.13-11.amzn2.0.2.aarch64.rpm",
        (
            "https://graviton-rpms.s3.amazonaws.com/amzn2-core-source_2021_01_26/"
            "amzn2-core-source/gsm-1.0.13-11.amzn2.0.2.src.rpm"
        ),
        # pytest-pep8.yaml
        "https://pypi.io/packages/source/p/pytest-pep8/pytest-pep8-1.0.7.tar.gz",
        # google-cloud-cpp.yaml
        "https://github.com/googleapis/google-cloud-cpp/archive/v2.31.0.tar.gz",
        # x264
        "http://download.videolan.org/pub/videolan/x264/snapshots/x264-snapshot-20191217-2245-stable.tar.bz2",
        # curl.yaml
        "https://curl.se/download/curl-8.11.0.tar.bz2",
        # libprotobuf.yaml
        "https://github.com/protocolbuffers/protobuf/archive/v25.3/libprotobuf-v25.3.tar.gz",
        "https://github.com/google/benchmark/archive/5b7683f49e1e9223cf9927b24f6fd3d6bd82e3f8.tar.gz",
        "https://github.com/google/googletest/archive/5ec7f0c4a113e2f18ac2c6cc7df51ad6afc24081.tar.gz",
    }
    match endpoint:
        case endpoint if endpoint in default_artifact_set:
            return MockHttpStreamResponse(200, "archive_files/dummy_project_01.tar.gz")
        # Error cases
        case "https://pypi.io/error_500.html":
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
    "recipe_file,version,expected_recipe_file",
    [
        ## Single-output Recipes##
        # NOTE: The SHA-256 hashes will be of the mocked archive files, not of the actual source code being referenced.
        ("types-toml.yaml", None, "bump_recipe/types-toml_build_num_1.yaml"),
        ("types-toml.yaml", "0.10.8.20240310", "bump_recipe/types-toml_version_bump.yaml"),
        # Specifieds rare `fn` field in `source` section
        ("boto.yaml", None, "bump_recipe/boto_build_num_1.yaml"),
        ("boto.yaml", "2.50.0", "bump_recipe/boto_version_bump.yaml"),
        ("huggingface_hub.yaml", None, "bump_recipe/huggingface_hub_build_num_1.yaml"),
        ("huggingface_hub.yaml", "0.24.6", "bump_recipe/huggingface_hub_version_bump.yaml"),
        # Does not use `version` variable, has a non-zero build number. Note that the URL is not parameterized on the
        # version field.
        ("gsm-amzn2-aarch64.yaml", None, "bump_recipe/gsm-amzn2-aarch64_build_num_6.yaml"),
        ("gsm-amzn2-aarch64.yaml", "2.0.20210721.2", "bump_recipe/gsm-amzn2-aarch64_version_bump.yaml"),
        # Has a `sha256` variable
        ("pytest-pep8.yaml", None, "bump_recipe/pytest-pep8_build_num_2.yaml"),
        ("pytest-pep8.yaml", "1.0.7", "bump_recipe/pytest-pep8_version_bump.yaml"),
        ("google-cloud-cpp.yaml", None, "bump_recipe/google-cloud-cpp_build_num_2.yaml"),
        ("google-cloud-cpp.yaml", "2.31.0", "bump_recipe/google-cloud-cpp_version_bump.yaml"),
        # Uses `sha256` variable and concatenated `version` variable.
        ("x264.yaml", None, "bump_recipe/x264_build_num_1.yaml"),
        # TODO: Add support for concatenated version strings
        # ("x264.yaml", "1!153.20191217", "bump_recipe/x264_version_bump.yaml"),
        ## Multi-output Recipes ##
        ("curl.yaml", None, "bump_recipe/curl_build_num_1.yaml"),
        ("curl.yaml", "8.11.0", "bump_recipe/curl_version_bump.yaml"),
        # NOTE: libprotobuf has multiple sources, on top of being multi-output
        ("libprotobuf.yaml", None, "bump_recipe/libprotobuf_build_num_1.yaml"),
        ("libprotobuf.yaml", "25.3", "bump_recipe/libprotobuf_version_bump.yaml"),
        # TODO add V1 test cases/support
        ## Version bump edge cases ##
        # NOTE: These have no source section, therefore all SHA-256 update attempts (and associated network requests)
        # should be skipped.
        ("bump_recipe/build_num_1.yaml", None, "bump_recipe/build_num_2.yaml"),
        ("bump_recipe/build_num_1.yaml", "0.10.8.6", "simple-recipe.yaml"),
        ("bump_recipe/build_num_42.yaml", None, "bump_recipe/build_num_43.yaml"),
        ("bump_recipe/build_num_42.yaml", "0.10.8.6", "simple-recipe.yaml"),
        ("bump_recipe/build_num_-1.yaml", None, "simple-recipe.yaml"),
        ("bump_recipe/build_num_-1.yaml", "0.10.8.6", "simple-recipe.yaml"),
    ],
)
def test_bump_recipe_cli(
    fs: FakeFilesystem,
    recipe_file: str,
    version: Optional[str],
    expected_recipe_file: str,
) -> None:
    """
    Test that the recipe file is successfully updated/bumped.

    :param fs: `pyfakefs` Fixture used to replace the file system
    :param recipe_file: Target recipe file to update
    :param version: (Optional) version to bump to. If `None`, this indicates `bump-recipe` should be run in
        increment-only mode.
    :param expected_recipe_file: Expected resulting recipe file
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path = get_test_path() / recipe_file
    expected_recipe_file_path = get_test_path() / expected_recipe_file

    cli_args: Final[list[str]] = (
        ["--build-num", str(recipe_file_path)] if version is None else ["-t", version, str(recipe_file_path)]
    )

    with patch("requests.get", new=mock_requests_get):
        result = runner.invoke(bump_recipe.bump_recipe, cli_args)

    # Ensure that we don't check against the file that was edited.
    assert recipe_file_path != expected_recipe_file_path
    # Read the edited file and check it against the expected file. We don't parse the recipe file as it isn't necessary.
    assert load_file(recipe_file_path) == load_file(expected_recipe_file_path)
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_recipe_exits_if_target_version_missing() -> None:
    """
    Ensures that the `--target-version` flag is required when `--build-num` is NOT provided.
    """
    runner = CliRunner()
    result = runner.invoke(bump_recipe.bump_recipe, [str(get_test_path() / "types-toml.yaml")])
    assert result.exit_code == ExitCode.CLICK_USAGE


def test_bump_recipe_increment_build_number_key_missing(fs: FakeFilesystem) -> None:
    """
    Test that a `/build/number` key is added and set to 0 when it's missing.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """
    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path: Final[Path] = get_test_path() / "bump_recipe/no_build_num.yaml"
    expected_recipe_file_path: Final[Path] = get_test_path() / "bump_recipe/build_num_added.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])

    # Ensure that we don't check against the file that was edited.
    assert recipe_file_path != expected_recipe_file_path
    assert load_file(recipe_file_path) == load_file(expected_recipe_file_path)
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_recipe_increment_build_number_not_int(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully case when the build number is not an integer,
    and we are trying to increment it.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path: Final[Path] = get_test_path() / "bump_recipe/non_int_build_num.yaml"

    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION


def test_bump_recipe_increment_build_num_key_not_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fixes the recipe file when the `/build/number` key is missing and we try to increment it's
    value.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path: Final[Path] = get_test_path() / "bump_recipe/no_build_num.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    # TODO: Can't compare directly to `simple-recipe.yaml` as the added key `/build/number` is not canonically sorted to
    # be in the standard position.
    assert load_recipe(recipe_file_path, RecipeReader).get_value("/build/number") == 0
    assert result.exit_code == ExitCode.SUCCESS


def test_bump_recipe_increment_no_build_key_found(fs: FakeFilesystem) -> None:
    """
    Test that the command fails gracefully when the build key is missing and we try to revert build number to zero.

    :param fs: `pyfakefs` Fixture used to replace the file system
    """

    runner = CliRunner()
    fs.add_real_directory(get_test_path(), read_only=False)

    recipe_file_path: Final[Path] = get_test_path() / "bump_recipe/no_build_key.yaml"
    result = runner.invoke(bump_recipe.bump_recipe, ["--build-num", str(recipe_file_path)])
    assert result.exit_code == ExitCode.ILLEGAL_OPERATION
