"""
File:           test_recipe_parser.py
Description:    Unit tests for the RecipeParser class
"""

from __future__ import annotations

from typing import Final

import pytest

from conda_recipe_manager.parser.enums import SchemaVersion, SelectorConflictMode
from conda_recipe_manager.parser.exceptions import JsonPatchValidationException
from conda_recipe_manager.parser.recipe_parser import RecipeParser
from conda_recipe_manager.types import JsonType, Primitives
from tests.file_loading import TEST_FILES_PATH, load_file, load_recipe

# Long multi-line description string found in the `simple-recipe.yaml` test file
SIMPLE_DESCRIPTION: Final[str] = (
    "This is a PEP '561 type stub package for the toml package.\n"
    "It can be used by type-checking tools like mypy, pyright,\n"
    "pytype, PyCharm, etc. to check code that uses toml."
)

# Multiline string used to validate interpretation of the various multiline variations YAML allows
QUICK_FOX_PIPE: Final[str] = "The quick brown\n{{fox}}\n\njumped over the lazy dog\n"
QUICK_FOX_PIPE_PLUS: Final[str] = "The quick brown\n{{fox}}\n\njumped over the lazy dog\n"
QUICK_FOX_PIPE_MINUS: Final[str] = "The quick brown\n{{fox}}\n\njumped over the lazy dog"
QUICK_FOX_CARROT: Final[str] = "The quick brown {{fox}}\njumped over the lazy dog\n"
QUICK_FOX_CARROT_PLUS: Final[str] = "The quick brown {{fox}}\njumped over the lazy dog\n"
QUICK_FOX_CARROT_MINUS: Final[str] = "The quick brown {{fox}}\njumped over the lazy dog"
# Substitution variants of the multiline string
QUICK_FOX_SUB_PIPE: Final[str] = "The quick brown\ntiger\n\njumped over the lazy dog\n"
QUICK_FOX_SUB_PIPE_PLUS: Final[str] = "The quick brown\ntiger\n\njumped over the lazy dog\n"
QUICK_FOX_SUB_PIPE_MINUS: Final[str] = "The quick brown\ntiger\n\njumped over the lazy dog"
QUICK_FOX_SUB_CARROT: Final[str] = "The quick brown tiger\njumped over the lazy dog\n"
QUICK_FOX_SUB_CARROT_PLUS: Final[str] = "The quick brown tiger\njumped over the lazy dog\n"
QUICK_FOX_SUB_CARROT_MINUS: Final[str] = "The quick brown tiger\njumped over the lazy dog"


## Construction and rendering sanity checks ##


@pytest.mark.parametrize(
    "file,schema_version",
    [
        ("types-toml.yaml", SchemaVersion.V0),
        ("v1_format/v1_types-toml.yaml", SchemaVersion.V1),
    ],
)
def test_construction(file: str, schema_version: SchemaVersion) -> None:
    """
    Tests the construction of a recipe parser instance with a simple, common example file.
    :param file: Recipe file to test with
    :param schema_version: Schema version to match
    """
    types_toml = load_file(f"{TEST_FILES_PATH}/{file}")
    parser = RecipeParser(types_toml)
    assert parser._init_content == types_toml  # pylint: disable=protected-access
    assert parser._vars_tbl == {  # pylint: disable=protected-access
        "name": "types-toml",
        "version": "0.10.8.6",
    }
    assert parser.get_schema_version() == schema_version
    assert not parser.is_modified()
    # TODO assert on selectors table

    # TODO assert on tree structure
    # assert parser._root == TODO


@pytest.mark.parametrize(
    "file,out_file",
    [
        ("simple-recipe.yaml", "simple-recipe_to_str.out"),
        ("v1_format/v1_simple-recipe.yaml", "v1_format/v1_simple-recipe_to_str.out"),
    ],
)
def test_str(file: str, out_file: str) -> None:
    """
    Tests rendering to a debug string
    :param file: Recipe file to test with
    :param out_file: Output string to match
    """
    parser = load_recipe(file)
    assert str(parser) == load_file(f"{TEST_FILES_PATH}/{out_file}")
    # Regression test: Run a function a second time to ensure that `SelectorInfo::__str__()` doesn't accidentally purge
    # the underlying stack when the string is being rendered.
    assert str(parser) == load_file(f"{TEST_FILES_PATH}/{out_file}")
    assert not parser.is_modified()


@pytest.mark.parametrize(
    "file,other_file",
    [
        ("simple-recipe.yaml", "types-toml.yaml"),
        ("v1_format/v1_simple-recipe.yaml", "v1_format/v1_types-toml.yaml"),
        ("v1_format/v1_simple-recipe.yaml", "simple-recipe.yaml"),
    ],
)
def test_eq(file: str, other_file: str) -> None:
    """
    Tests equivalency function
    :param file: Recipe file to test with
    :param other_file: "Other" recipe file to check against
    """
    parser0 = load_recipe(file)
    parser1 = load_recipe(file)
    parser2 = load_recipe(other_file)
    assert parser0 == parser1
    assert parser0 != parser2
    assert not parser0.is_modified()
    assert not parser1.is_modified()
    assert not parser2.is_modified()


def test_loading_obj_in_list() -> None:
    """
    Regression test: at one point, the parser would crash loading this file, containing an object in a list.
    """
    replace = load_file(f"{TEST_FILES_PATH}/simple-recipe_test_patch_replace.yaml")
    parser = RecipeParser(replace)
    assert parser.render() == replace


@pytest.mark.parametrize(
    "file",
    [
        # V0 Recipe Files
        "types-toml.yaml",  # "Easy-difficulty" recipe, representative of common/simple recipes.
        "simple-recipe.yaml",  # "Medium-difficulty" recipe, containing several contrived examples
        "multi-output.yaml",  # Contains a multi-output recipe
        "huggingface_hub.yaml",  # Contains a blank lines in a multiline string
        "simple-recipe_multiline_strings.yaml",  # Contains multiple multiline strings, using various operators
        "curl.yaml",  # Complex, multi-output recipe
        "gsm-amzn2-aarch64.yaml",  # Regression test: Contains `- '*'` string that failed to parse
        "pytest-pep8.yaml",
        "google-cloud-cpp.yaml",
        "dynamic-linking.yaml",
        # V1 Recipe Files
        "v1_format/v1_types-toml.yaml",
        "v1_format/v1_simple-recipe.yaml",
        "v1_format/v1_multi-output.yaml",
        "v1_format/v1_huggingface_hub.yaml",
        "v1_format/v1_curl.yaml",
        "v1_format/v1_pytest-pep8.yaml",
        "v1_format/v1_google-cloud-cpp.yaml",
        "v1_format/v1_dynamic-linking.yaml",
    ],
)
def test_round_trip(file: str) -> None:
    """
    Test "eating our own dog food"/round-tripping the parser: Take a recipe, construct a parser, re-render and
    ensure the output matches the input.
    """
    expected: Final[str] = load_file(f"{TEST_FILES_PATH}/{file}")
    parser = RecipeParser(expected)
    assert parser.render() == expected


@pytest.mark.parametrize(
    "file,substitute,expected",
    [
        # V0 Recipes
        (
            "simple-recipe.yaml",
            False,
            {
                "about": {
                    "description": SIMPLE_DESCRIPTION,
                    "license": "Apache-2.0 AND MIT",
                    "summary": "This is a small recipe for testing",
                },
                "test_var_usage": {
                    "foo": "{{ version }}",
                    "bar": [
                        "baz",
                        "{{ zz_non_alpha_first }}",
                        "blah",
                        "This {{ name }} is silly",
                        "last",
                    ],
                },
                "build": {"is_true": True, "skip": True, "number": 0},
                "package": {"name": "{{ name|lower }}"},
                "requirements": {
                    "empty_field1": None,
                    "host": ["setuptools", "fakereq"],
                    "empty_field2": None,
                    "run": ["python"],
                    "empty_field3": None,
                },
                "multi_level": {
                    "list_3": ["ls", "sl", "cowsay"],
                    "list_2": ["cat", "bat", "mat"],
                    "list_1": ["foo", "bar"],
                },
            },
        ),
        (
            "simple-recipe.yaml",
            True,
            {
                "about": {
                    "description": SIMPLE_DESCRIPTION,
                    "license": "Apache-2.0 AND MIT",
                    "summary": "This is a small recipe for testing",
                },
                "test_var_usage": {
                    "foo": "0.10.8.6",
                    "bar": [
                        "baz",
                        42,
                        "blah",
                        "This types-toml is silly",
                        "last",
                    ],
                },
                "build": {"is_true": True, "skip": True, "number": 0},
                "package": {"name": "types-toml"},
                "requirements": {
                    "empty_field1": None,
                    "host": ["setuptools", "fakereq"],
                    "empty_field2": None,
                    "run": ["python"],
                    "empty_field3": None,
                },
                "multi_level": {
                    "list_3": ["ls", "sl", "cowsay"],
                    "list_2": ["cat", "bat", "mat"],
                    "list_1": ["foo", "bar"],
                },
            },
        ),
        (
            "simple-recipe_multiline_strings.yaml",
            False,
            {
                "about": {
                    "description0": QUICK_FOX_PIPE,
                    "description1": QUICK_FOX_PIPE_PLUS,
                    "description2": QUICK_FOX_PIPE_MINUS,
                    "description3": QUICK_FOX_CARROT,
                    "description4": QUICK_FOX_CARROT_PLUS,
                    "description5": QUICK_FOX_CARROT_MINUS,
                    "license": "Apache-2.0 AND MIT",
                    "summary": "This is a small recipe for testing",
                },
                "test_var_usage": {
                    "foo": "{{ version }}",
                    "bar": [
                        "baz",
                        "{{ zz_non_alpha_first }}",
                        "blah",
                        "This {{ name }} is silly",
                        "last",
                    ],
                },
                "build": {"is_true": True, "skip": True, "number": 0},
                "package": {"name": "{{ name|lower }}"},
            },
        ),
        (
            "simple-recipe_multiline_strings.yaml",
            True,
            {
                "about": {
                    "description0": QUICK_FOX_SUB_PIPE,
                    "description1": QUICK_FOX_SUB_PIPE_PLUS,
                    "description2": QUICK_FOX_SUB_PIPE_MINUS,
                    "description3": QUICK_FOX_SUB_CARROT,
                    "description4": QUICK_FOX_SUB_CARROT_PLUS,
                    "description5": QUICK_FOX_SUB_CARROT_MINUS,
                    "license": "Apache-2.0 AND MIT",
                    "summary": "This is a small recipe for testing",
                },
                "test_var_usage": {
                    "foo": "0.10.8.6",
                    "bar": [
                        "baz",
                        42,
                        "blah",
                        "This types-toml is silly",
                        "last",
                    ],
                },
                "build": {"is_true": True, "skip": True, "number": 0},
                "package": {"name": "types-toml"},
            },
        ),
    ],
)
def test_render_to_object(file: str, substitute: bool, expected: JsonType) -> None:
    """
    Tests rendering a recipe to an object format.
    TODO: Does not work with V1 recipes; if/then selectors crash with KeyError
    :param file: File to load and test against
    :param substitute: True to run the function with JINJA substitutions on, False for off
    :param expected: Expected value to return
    """
    parser = load_recipe(file)
    assert parser.render_to_object(substitute) == expected


def test_render_to_object_multi_output() -> None:
    """
    Tests rendering a recipe to an object format.
    """
    parser = load_recipe("multi-output.yaml")
    assert parser.render_to_object() == {
        "outputs": [
            {
                "name": "libdb",
                "build": {
                    "run_exports": ["bar"],
                },
                "test": {
                    "commands": [
                        "test -f ${PREFIX}/lib/libdb${SHLIB_EXT}",
                        r"if not exist %LIBRARY_BIN%\libdb%SHLIB_EXT%",
                    ],
                },
            },
            {
                "name": "db",
                "requirements": {
                    "build": [
                        "foo3",
                        "foo2",
                        "{{ compiler('c') }}",
                        "{{ compiler('cxx') }}",
                    ],
                    "run": ["foo"],
                },
                "test": {
                    "commands": [
                        "db_archive -m hello",
                    ]
                },
            },
        ]
    }


## Values ##


@pytest.mark.parametrize(
    "file,expected",
    [
        (
            "simple-recipe.yaml",
            [
                "/package/name",
                "/build/number",
                "/build/skip",
                "/build/is_true",
                "/requirements/empty_field1",
                "/requirements/host/0",
                "/requirements/host/1",
                "/requirements/empty_field2",
                "/requirements/run/0",
                "/requirements/empty_field3",
                "/about/summary",
                "/about/description",
                "/about/license",
                "/multi_level/list_1/0",
                "/multi_level/list_1/1",
                "/multi_level/list_2/0",
                "/multi_level/list_2/1",
                "/multi_level/list_2/2",
                "/multi_level/list_3/0",
                "/multi_level/list_3/1",
                "/multi_level/list_3/2",
                "/test_var_usage/foo",
                "/test_var_usage/bar/0",
                "/test_var_usage/bar/1",
                "/test_var_usage/bar/2",
                "/test_var_usage/bar/3",
                "/test_var_usage/bar/4",
            ],
        ),
        (
            "v1_format/v1_simple-recipe.yaml",
            [
                "/schema_version",
                "/context/zz_non_alpha_first",
                "/context/name",
                "/context/version",
                "/package/name",
                "/build/number",
                "/build/skip",
                "/build/is_true",
                "/requirements/empty_field1",
                "/requirements/host/0/if",
                "/requirements/host/0/then",
                "/requirements/host/1/if",
                "/requirements/host/1/then",
                "/requirements/empty_field2",
                "/requirements/run/0",
                "/requirements/empty_field3",
                "/about/summary",
                "/about/description",
                "/about/license",
                "/multi_level/list_1/0",
                "/multi_level/list_1/1",
                "/multi_level/list_2/0",
                "/multi_level/list_2/1",
                "/multi_level/list_2/2",
                "/multi_level/list_3/0",
                "/multi_level/list_3/1",
                "/multi_level/list_3/2",
                "/test_var_usage/foo",
                "/test_var_usage/bar/0",
                "/test_var_usage/bar/1",
                "/test_var_usage/bar/2",
                "/test_var_usage/bar/3",
                "/test_var_usage/bar/4",
            ],
        ),
    ],
)
def test_list_value_paths(file: str, expected: list[str]) -> None:
    """
    Tests retrieval of all value paths
    :param file: Recipe file to test with
    :param expected: Expected result
    """
    parser = load_recipe(file)
    assert parser.list_value_paths() == expected


@pytest.mark.parametrize(
    "file,path,expected",
    [
        ## simple-recipe.yaml ##
        ("simple-recipe.yaml", "/schema_version", False),
        ("simple-recipe.yaml", "/build/number", True),
        ("simple-recipe.yaml", "/build/number/", True),
        ("simple-recipe.yaml", "/build", True),
        ("simple-recipe.yaml", "/requirements/host/0", True),
        ("simple-recipe.yaml", "/requirements/host/1", True),
        ("simple-recipe.yaml", "/multi_level/list_1/1", True),  # Comments in lists could throw-off array indexing
        ("simple-recipe.yaml", "/invalid/fake/path", False),
        ## multi-output.yaml ##
        ("multi-output.yaml", "/outputs/0/build/run_exports", True),
        ("multi-output.yaml", "/outputs/1/build/run_exports", False),
        ("multi-output.yaml", "/outputs/1/requirements/0", False),  # Should fail as this is an object, not a list
        ("multi-output.yaml", "/outputs/1/requirements/build/0", True),
        ("multi-output.yaml", "/outputs/1/requirements/build/1", True),
        ("multi-output.yaml", "/outputs/1/requirements/build/2", True),
        ("multi-output.yaml", "/outputs/1/requirements/build/3", True),
        ("multi-output.yaml", "/outputs/1/requirements/build/4", False),
        ## v1_simple-recipe.yaml ##
        ("v1_format/v1_simple-recipe.yaml", "/schema_version", True),
        ("v1_format/v1_simple-recipe.yaml", "/build/number", True),
        ("v1_format/v1_simple-recipe.yaml", "/build/number/", True),
        ("v1_format/v1_simple-recipe.yaml", "/build", True),
        ("v1_format/v1_simple-recipe.yaml", "/requirements/host/0", True),
        ("v1_format/v1_simple-recipe.yaml", "/requirements/host/1", True),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/multi_level/list_1/1",
            True,
        ),  # Comments in lists could throw-off array indexing
        ("v1_format/v1_simple-recipe.yaml", "/invalid/fake/path", False),
    ],
)
def test_contains_value(file: str, path: str, expected: bool) -> None:
    """
    Tests if a path exists in a parsed recipe file.
    :param file: File to work against
    :param path: Target input path
    :param expected: Expected result of the test
    """
    parser = load_recipe(file)
    assert parser.contains_value(path) == expected
    assert not parser.is_modified()


@pytest.mark.parametrize(
    "file,path,sub_vars,expected",
    [
        ## simple-recipe.yaml ##
        # Return a single value
        ("simple-recipe.yaml", "/build/number", False, 0),
        ("simple-recipe.yaml", "/build/number/", False, 0),
        # Return a compound value
        (
            "simple-recipe.yaml",
            "/build",
            False,
            {
                "number": 0,
                "skip": True,
                "is_true": True,
            },
        ),
        (
            "simple-recipe.yaml",
            "/build/",
            False,
            {
                "number": 0,
                "skip": True,
                "is_true": True,
            },
        ),
        # Return a Jinja value
        ("simple-recipe.yaml", "/package/name", False, "{{ name|lower }}"),
        ("simple-recipe.yaml", "/package/name", True, "types-toml"),
        ("simple-recipe.yaml", "/test_var_usage/foo", False, "{{ version }}"),
        ("simple-recipe.yaml", "/test_var_usage/foo", True, "0.10.8.6"),
        ("simple-recipe.yaml", "/test_var_usage/bar/1", False, "{{ zz_non_alpha_first }}"),
        ("simple-recipe.yaml", "/test_var_usage/bar/1", True, 42),
        # Return a value in a list
        ("simple-recipe.yaml", "/requirements/host", False, ["setuptools", "fakereq"]),
        ("simple-recipe.yaml", "/requirements/host/", False, ["setuptools", "fakereq"]),
        ("simple-recipe.yaml", "/requirements/host", True, ["setuptools", "fakereq"]),
        ("simple-recipe.yaml", "/requirements/host/0", False, "setuptools"),
        ("simple-recipe.yaml", "/requirements/host/1", False, "fakereq"),
        # Regression: A list containing 1 value may be interpreted as the base type by YAML parsers. This can wreak
        # havoc on type safety.
        ("simple-recipe.yaml", "/requirements/run", False, ["python"]),
        # Return a multiline string
        ("simple-recipe.yaml", "/about/description", False, SIMPLE_DESCRIPTION),
        ("simple-recipe.yaml", "/about/description/", False, SIMPLE_DESCRIPTION),
        # Comments in lists could throw-off array indexing
        ("simple-recipe.yaml", "/multi_level/list_1/1", False, "bar"),
        # Render a recursive, complex type.
        (
            "simple-recipe.yaml",
            "/test_var_usage",
            False,
            {
                "foo": "{{ version }}",
                "bar": [
                    "baz",
                    "{{ zz_non_alpha_first }}",
                    "blah",
                    "This {{ name }} is silly",
                    "last",
                ],
            },
        ),
        (
            "simple-recipe.yaml",
            "/test_var_usage",
            True,
            {
                "foo": "0.10.8.6",
                "bar": [
                    "baz",
                    42,
                    "blah",
                    "This types-toml is silly",
                    "last",
                ],
            },
        ),
        (
            "simple-recipe.yaml",
            "/test_var_usage/bar",
            True,
            [
                "baz",
                42,
                "blah",
                "This types-toml is silly",
                "last",
            ],
        ),
        ## simple-recipe_multiline_strings.yaml ##
        # Return multiline string variants
        ("simple-recipe_multiline_strings.yaml", "/about/description0", False, QUICK_FOX_PIPE),
        ("simple-recipe_multiline_strings.yaml", "/about/description1", False, QUICK_FOX_PIPE_PLUS),
        ("simple-recipe_multiline_strings.yaml", "/about/description2", False, QUICK_FOX_PIPE_MINUS),
        ("simple-recipe_multiline_strings.yaml", "/about/description3", False, QUICK_FOX_CARROT),
        ("simple-recipe_multiline_strings.yaml", "/about/description4", False, QUICK_FOX_CARROT_PLUS),
        ("simple-recipe_multiline_strings.yaml", "/about/description5", False, QUICK_FOX_CARROT_MINUS),
        # Return multiline string variants, with substitution
        ("simple-recipe_multiline_strings.yaml", "/about/description0", True, QUICK_FOX_SUB_PIPE),
        ("simple-recipe_multiline_strings.yaml", "/about/description1", True, QUICK_FOX_SUB_PIPE_PLUS),
        ("simple-recipe_multiline_strings.yaml", "/about/description2", True, QUICK_FOX_SUB_PIPE_MINUS),
        ("simple-recipe_multiline_strings.yaml", "/about/description3", True, QUICK_FOX_SUB_CARROT),
        ("simple-recipe_multiline_strings.yaml", "/about/description4", True, QUICK_FOX_SUB_CARROT_PLUS),
        ("simple-recipe_multiline_strings.yaml", "/about/description5", True, QUICK_FOX_SUB_CARROT_MINUS),
        ## v1_simple-recipe.yaml ##
        ("v1_format/v1_simple-recipe.yaml", "/build/number", False, 0),
        ("v1_format/v1_simple-recipe.yaml", "/build/number/", False, 0),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/build",
            False,
            {
                "number": 0,
                "skip": 'match(python, "<3.7")',
                "is_true": True,
            },
        ),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/build/",
            False,
            {
                "number": 0,
                "skip": 'match(python, "<3.7")',
                "is_true": True,
            },
        ),
        ("v1_format/v1_simple-recipe.yaml", "/package/name", False, "${{ name|lower }}"),
        ("v1_format/v1_simple-recipe.yaml", "/package/name", True, "types-toml"),
        ("v1_format/v1_simple-recipe.yaml", "/test_var_usage/foo", False, "${{ version }}"),
        ("v1_format/v1_simple-recipe.yaml", "/test_var_usage/foo", True, "0.10.8.6"),
        ("v1_format/v1_simple-recipe.yaml", "/test_var_usage/bar/1", False, "${{ zz_non_alpha_first }}"),
        ("v1_format/v1_simple-recipe.yaml", "/test_var_usage/bar/1", True, 42),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/requirements/host",
            False,
            [{"if": "unix", "then": "setuptools"}, {"if": "unix", "then": "fakereq"}],
        ),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/requirements/host/",
            False,
            [{"if": "unix", "then": "setuptools"}, {"if": "unix", "then": "fakereq"}],
        ),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/requirements/host",
            True,
            [{"if": "unix", "then": "setuptools"}, {"if": "unix", "then": "fakereq"}],
        ),
        # TODO fix V1_SUPPORT: yaml.parser.ParserError: while parsing a block collection
        # ("v1_format/v1_simple-recipe.yaml", "/requirements/host/0", False, {"if": "unix", "then": "setuptools"}),
        # ("v1_format/v1_simple-recipe.yaml", "/requirements/host/1", False, {"if": "unix", "then": "fakereq"}),
        ("v1_format/v1_simple-recipe.yaml", "/requirements/host/0/then", False, "setuptools"),
        ("v1_format/v1_simple-recipe.yaml", "/requirements/host/1/then", False, "fakereq"),
        ("v1_format/v1_simple-recipe.yaml", "/requirements/run", False, ["python"]),
        ("v1_format/v1_simple-recipe.yaml", "/about/description", False, SIMPLE_DESCRIPTION),
        ("v1_format/v1_simple-recipe.yaml", "/about/description/", False, SIMPLE_DESCRIPTION),
        ("v1_format/v1_simple-recipe.yaml", "/multi_level/list_1/1", False, "bar"),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/test_var_usage",
            False,
            {
                "foo": "${{ version }}",
                "bar": [
                    "baz",
                    "${{ zz_non_alpha_first }}",
                    "blah",
                    "This ${{ name }} is silly",
                    "last",
                ],
            },
        ),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/test_var_usage",
            True,
            {
                "foo": "0.10.8.6",
                "bar": [
                    "baz",
                    42,
                    "blah",
                    "This types-toml is silly",
                    "last",
                ],
            },
        ),
        (
            "v1_format/v1_simple-recipe.yaml",
            "/test_var_usage/bar",
            True,
            [
                "baz",
                42,
                "blah",
                "This types-toml is silly",
                "last",
            ],
        ),
        ## multi-output.yaml ##
        ("multi-output.yaml", "/outputs/0/build/run_exports/0", False, "bar"),
        ("multi-output.yaml", "/outputs/0/build/run_exports", False, ["bar"]),
        ("multi-output.yaml", "/outputs/0/build", False, {"run_exports": ["bar"]}),
        # TODO FIX: This case
        # (
        #    "multi-output.yaml",
        #    "/outputs/1",
        #    False,
        #    {
        #        "name": "db",
        #        "requirements": {
        #            "build": ["foo3", "foo2", "{{ compiler('c') }}", "{{ compiler('cxx') }}"],
        #            "run": ["foo"],
        #        },
        #        "test": {"commands": ["db_archive -m hello"]},
        #    },
        # ),
    ],
)
def test_get_value(file: str, path: str, sub_vars: bool, expected: JsonType) -> None:
    """
    Tests retrieval of a value from a parsed YAML example.
    :param file: File to work against
    :param path: Target input path
    :param sub_vars: True to substitute JINJA variables. False otherwise.
    :param expected: Expected result of the test
    """
    parser = load_recipe(file)
    assert parser.get_value(path, sub_vars=sub_vars) == expected
    assert not parser.is_modified()


@pytest.mark.parametrize("file", ["simple-recipe.yaml", "v1_format/v1_simple-recipe.yaml"])
def test_get_value_not_found(file: str) -> None:
    """
    Tests failure to retrieve a value from a parsed YAML example.
    :param file: File to work against
    """
    parser = load_recipe(file)
    # Path not found cases
    with pytest.raises(KeyError):
        parser.get_value("/invalid/fake/path")
    assert parser.get_value("/invalid/fake/path", 42) == 42
    # Tests that a user can pass `None` without throwing
    assert parser.get_value("/invalid/fake/path", None) is None
    assert not parser.is_modified()


@pytest.mark.parametrize(
    "file,value,expected",
    [
        ## V0 Format ##
        (
            "simple-recipe.yaml",
            None,
            [
                "/requirements/empty_field1",
                "/requirements/empty_field2",
                "/requirements/empty_field3",
            ],
        ),
        ("simple-recipe.yaml", "fakereq", ["/requirements/host/1"]),
        ("simple-recipe.yaml", True, ["/build/skip", "/build/is_true"]),
        ("simple-recipe.yaml", "foo", ["/multi_level/list_1/0"]),
        ("simple-recipe.yaml", "Apache-2.0 AND MIT", ["/about/license"]),
        ("simple-recipe.yaml", 43, []),
        ("simple-recipe.yaml", "fooz", []),
        ("simple-recipe.yaml", "", []),
        ## V1 Format ##
        (
            "v1_format/v1_simple-recipe.yaml",
            None,
            [
                "/requirements/empty_field1",
                "/requirements/empty_field2",
                "/requirements/empty_field3",
            ],
        ),
        ("v1_format/v1_simple-recipe.yaml", "fakereq", ["/requirements/host/1/then"]),
        ("v1_format/v1_simple-recipe.yaml", True, ["/build/is_true"]),
        ("v1_format/v1_simple-recipe.yaml", "foo", ["/multi_level/list_1/0"]),
        ("v1_format/v1_simple-recipe.yaml", "Apache-2.0 AND MIT", ["/about/license"]),
        ("v1_format/v1_simple-recipe.yaml", 43, []),
        ("v1_format/v1_simple-recipe.yaml", "fooz", []),
        ("v1_format/v1_simple-recipe.yaml", "", []),
    ],
)
def test_find_value(file: str, value: Primitives, expected: list[str]) -> None:
    """
    Tests finding a value from a parsed YAML example.
    :param file: File to work against
    :param value: Target value
    :param expected: Expected result of the test
    """
    parser = load_recipe(file)
    assert parser.find_value(value) == expected
    assert not parser.is_modified()


@pytest.mark.parametrize(
    "file,value",
    [
        ("simple-recipe.yaml", ["foo", "bar"]),
        ("simple-recipe.yaml", ("foo", "bar")),
        ("simple-recipe.yaml", {"foo": "bar"}),
        ("v1_format/v1_simple-recipe.yaml", ["foo", "bar"]),
        ("v1_format/v1_simple-recipe.yaml", ("foo", "bar")),
        ("v1_format/v1_simple-recipe.yaml", {"foo": "bar"}),
    ],
)
def test_find_value_raises(file: str, value: Primitives) -> None:
    """
    Tests finding a value from a parsed YAML example that should throw a `ValueError`.
    :param file: File to work against
    :param value: Target value
    """
    parser = load_recipe(file)
    with pytest.raises(ValueError):
        parser.find_value(value)
    assert not parser.is_modified()


## Dependencies ##


@pytest.mark.parametrize(
    "file,expected",
    [
        ("multi-output.yaml", True),
        ("simple-recipe.yaml", False),
        ("v1_format/v1_multi-output.yaml", True),
        ("v1_format/v1_simple-recipe.yaml", False),
    ],
)
def test_is_multi_output(file: str, expected: bool) -> None:
    """
    Validates if a recipe is in the multi-output format
    :param file: File to test against
    :param expected: Expected output
    """
    assert load_recipe(file).is_multi_output() == expected


@pytest.mark.parametrize(
    "file,expected",
    [
        ("multi-output.yaml", ["/", "/outputs/0", "/outputs/1"]),
        ("simple-recipe.yaml", ["/"]),
        ("simple-recipe_comment_in_requirements.yaml", ["/"]),
        ("huggingface_hub.yaml", ["/"]),
    ],
)
def test_get_package_paths(file: str, expected: list[str]) -> None:
    """
    Validates fetching paths containing recipe dependencies
    :param file: File to test against
    :param expected: Expected output
    """
    assert load_recipe(file).get_package_paths() == expected


@pytest.mark.parametrize(
    "base,ext,expected",
    [
        ("", "", "/"),
        ("/", "/foo/bar", "/foo/bar"),
        ("/", "foo/bar", "/foo/bar"),
        ("/foo/bar", "baz", "/foo/bar/baz"),
        ("/foo/bar", "/baz", "/foo/bar/baz"),
    ],
)
def test_append_to_path(base: str, ext: str, expected: str) -> None:
    """
    :param base: Base string path
    :param ext: Path to extend the base path with
    :param expected: Expected output
    """
    assert RecipeParser.append_to_path(base, ext) == expected


@pytest.mark.parametrize(
    "file,expected",
    [
        (
            "multi-output.yaml",
            [
                "/outputs/1/requirements/build/0",
                "/outputs/1/requirements/build/1",
                "/outputs/1/requirements/build/2",
                "/outputs/1/requirements/build/3",
                "/outputs/1/requirements/run/0",
            ],
        ),
        ("simple-recipe.yaml", ["/requirements/host/0", "/requirements/host/1", "/requirements/run/0"]),
        (
            "simple-recipe_comment_in_requirements.yaml",
            ["/requirements/host/0", "/requirements/host/1", "/requirements/run/0"],
        ),
        (
            "huggingface_hub.yaml",
            [
                "/requirements/host/0",
                "/requirements/host/1",
                "/requirements/host/2",
                "/requirements/host/3",
                "/requirements/run/0",
                "/requirements/run/1",
                "/requirements/run/2",
                "/requirements/run/3",
                "/requirements/run/4",
                "/requirements/run/5",
                "/requirements/run/6",
                "/requirements/run/7",
                "/requirements/run/8",
                "/requirements/run_constrained/0",
                "/requirements/run_constrained/1",
                "/requirements/run_constrained/2",
            ],
        ),
    ],
)
def test_get_dependency_paths(file: str, expected: list[str]) -> None:
    """
    Validates fetching paths containing recipe dependencies
    :param file: File to test against
    :param expected: Expected output
    """
    assert load_recipe(file).get_dependency_paths() == expected


## Variables ##


def test_list_variable() -> None:
    """
    Validates the list of variables found
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.list_variables() == ["zz_non_alpha_first", "name", "version"]
    assert not parser.is_modified()


def test_contains_variable() -> None:
    """
    Validates checking if a variable exists in a recipe
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.contains_variable("zz_non_alpha_first")
    assert parser.contains_variable("name")
    assert parser.contains_variable("version")
    assert not parser.contains_variable("fake_var")
    assert not parser.is_modified()


def test_get_variable() -> None:
    """
    Tests the value returned from fetching a variable
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.get_variable("zz_non_alpha_first") == 42
    assert parser.get_variable("name") == "types-toml"
    assert parser.get_variable("version") == "0.10.8.6"
    with pytest.raises(KeyError):
        parser.get_variable("fake_var")
    assert parser.get_variable("fake_var", 43) == 43
    # Tests that a user can pass `None` without throwing
    assert parser.get_variable("fake_var", None) is None
    assert not parser.is_modified()


def test_set_variable() -> None:
    """
    Tests setting and adding a variable
    """
    parser = load_recipe("simple-recipe.yaml")
    parser.set_variable("name", "foobar")
    parser.set_variable("zz_non_alpha_first", 24)
    # Ensure a missing variable gets added
    parser.set_variable("DNE", "The limit doesn't exist")
    # Validate
    assert parser.is_modified()
    assert parser.list_variables() == [
        "zz_non_alpha_first",
        "name",
        "version",
        "DNE",
    ]
    assert parser.get_variable("name") == "foobar"
    assert parser.get_variable("zz_non_alpha_first") == 24
    assert parser.get_variable("DNE") == "The limit doesn't exist"


def test_del_variable() -> None:
    """
    Tests deleting a variable
    """
    parser = load_recipe("simple-recipe.yaml")
    parser.del_variable("name")
    # Ensure a missing var doesn't crash a delete
    parser.del_variable("DNE")
    # Validate
    assert parser.is_modified()
    assert parser.list_variables() == ["zz_non_alpha_first", "version"]
    with pytest.raises(KeyError):
        parser.get_variable("name")


def test_get_variable_references() -> None:
    """
    Tests generating a list of paths that use a variable
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.get_variable_references("version") == [
        "/test_var_usage/foo",
    ]
    assert parser.get_variable_references("zz_non_alpha_first") == [
        "/test_var_usage/bar/1",
    ]
    assert parser.get_variable_references("name") == [
        "/package/name",
        "/test_var_usage/bar/3",
    ]
    assert not parser.is_modified()


## Selectors ##


def test_list_selectors() -> None:
    """
    Validates the list of selectors found
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.list_selectors() == ["[unix]", "[py<37]", "[unix and win]"]
    assert not parser.is_modified()


def test_contains_selectors() -> None:
    """
    Validates checking if a selector exists in a recipe
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.contains_selector("[py<37]")
    assert parser.contains_selector("[unix]")
    assert not parser.contains_selector("[fake selector]")
    assert not parser.is_modified()


def test_get_selector_paths() -> None:
    """
    Tests the paths returned from fetching a selector
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.get_selector_paths("[py<37]") == ["/build/skip"]
    assert parser.get_selector_paths("[unix]") == [
        "/package/name",
        "/requirements/host/0",
        "/requirements/host/1",
    ]
    assert not parser.get_selector_paths("[fake selector]")
    assert not parser.is_modified()


@pytest.mark.parametrize(
    "file,path,expected",
    [
        ("simple-recipe.yaml", "/build/skip", True),
        ("simple-recipe.yaml", "/requirements/host/0", True),
        ("simple-recipe.yaml", "/requirements/host/1", True),
        ("simple-recipe.yaml", "/requirements/empty_field2", True),
        ("simple-recipe.yaml", "/requirements/run/0", False),
        ("simple-recipe.yaml", "/requirements/run", False),
        ("simple-recipe.yaml", "/fake/path", False),
    ],
)
def test_contains_selector_at_path(file: str, path: str, expected: bool) -> None:
    """
    Tests checking if a selector exists on a given path
    :param file: File to run against
    :param path: Path to check
    :param expected: Expected value
    """
    assert load_recipe(file).contains_selector_at_path(path) == expected


@pytest.mark.parametrize(
    "file,path,expected",
    [
        ("simple-recipe.yaml", "/build/skip", "[py<37]"),
        ("simple-recipe.yaml", "/requirements/host/0", "[unix]"),
        ("simple-recipe.yaml", "/requirements/host/1", "[unix]"),
        ("simple-recipe.yaml", "/requirements/empty_field2", "[unix and win]"),
    ],
)
def test_get_selector_at_path_exists(file: str, path: str, expected: str) -> None:
    """
    Tests cases where a selector exists on a path
    :param file: File to run against
    :param path: Path to check
    :param expected: Expected value
    """
    assert load_recipe(file).get_selector_at_path(path) == expected


def test_get_selector_at_path_dne() -> None:
    """
    Tests edge cases where `get_selector_at_path()` should fail correctly OR
    handles non-existent selectors gracefully
    """
    parser = load_recipe("simple-recipe.yaml")
    # Path does not exist
    with pytest.raises(KeyError):
        parser.get_selector_at_path("/fake/path")
    # No default was provided
    with pytest.raises(KeyError):
        parser.get_selector_at_path("/requirements/run/0")
    # Invalid default was provided
    with pytest.raises(ValueError):
        parser.get_selector_at_path("/requirements/run/0", "not a selector")

    # Valid default was provided
    assert parser.get_selector_at_path("/requirements/run/0", "[unix]") == "[unix]"


def test_add_selector() -> None:
    """
    Tests adding a selector to a recipe
    """
    parser = load_recipe("simple-recipe.yaml")
    # Test that selector validation is working
    with pytest.raises(KeyError):
        parser.add_selector("/package/path/to/fake/value", "[unix]")
    with pytest.raises(ValueError):
        parser.add_selector("/build/number", "bad selector")
    assert not parser.is_modified()

    # Add selectors to lines without existing selectors
    parser.add_selector("/requirements/empty_field3", "[unix]")
    parser.add_selector("/multi_level/list_1/0", "[unix]")
    parser.add_selector("/build/number", "[win]")
    parser.add_selector("/multi_level/list_2/1", "[win]")
    assert parser.get_selector_paths("[unix]") == [
        "/package/name",
        "/requirements/host/0",
        "/requirements/host/1",
        "/requirements/empty_field3",
        "/multi_level/list_1/0",
    ]
    assert parser.get_selector_paths("[win]") == [
        "/build/number",
        "/multi_level/list_2/1",
    ]

    # Add selectors to existing selectors
    parser.add_selector("/requirements/host/0", "[win]", SelectorConflictMode.REPLACE)
    assert parser.get_selector_paths("[win]") == [
        "/build/number",
        "/requirements/host/0",
        "/multi_level/list_2/1",
    ]
    parser.add_selector("/requirements/host/1", "[win]", SelectorConflictMode.AND)
    assert parser.get_selector_paths("[unix and win]") == ["/requirements/host/1", "/requirements/empty_field2"]
    parser.add_selector("/build/skip", "[win]", SelectorConflictMode.OR)
    assert parser.get_selector_paths("[py<37 or win]") == ["/build/skip"]
    parser.add_selector("/requirements/run/0", "[win]", SelectorConflictMode.AND)
    assert parser.get_selector_paths("[win]") == [
        "/build/number",
        "/requirements/host/0",
        "/requirements/run/0",
        "/multi_level/list_2/1",
    ]

    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_add_selector.yaml")
    assert parser.is_modified()


def test_remove_selector() -> None:
    """
    Tests removing a selector to a recipe
    """
    parser = load_recipe("simple-recipe.yaml")
    # Test that selector validation is working
    with pytest.raises(KeyError):
        parser.remove_selector("/package/path/to/fake/value")

    # Don't fail when a selector doesn't exist on a line
    assert parser.remove_selector("/build/number") is None
    # Don't remove a non-selector comment
    assert parser.remove_selector("/requirements/run/0") is None
    assert not parser.is_modified()

    # Remove a selector
    assert parser.remove_selector("/package/name") == "[unix]"
    assert parser.get_selector_paths("[unix]") == [
        "/requirements/host/0",
        "/requirements/host/1",
    ]
    # Remove a selector with a comment
    assert parser.remove_selector("/requirements/host/1") == "[unix]"
    assert parser.get_selector_paths("[unix]") == [
        "/requirements/host/0",
    ]
    # Remove a selector with a "double comment (extra `#` symbols used)"
    assert parser.remove_selector("/requirements/empty_field2") == "[unix and win]"
    assert not parser.get_selector_paths("[unix and win]")

    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_remove_selector.yaml")
    assert parser.is_modified()


## Comments ##


@pytest.mark.parametrize(
    "file,expected",
    [
        (
            "simple-recipe.yaml",
            {
                "/requirements/host/1": "# selector with comment",
                "/requirements/empty_field2": "# selector with comment with comment symbol",
                "/requirements/run/0": "# not a selector",
            },
        ),
        ("huggingface_hub.yaml", {}),
        ("multi-output.yaml", {}),
        (
            "curl.yaml",
            {
                "/outputs/0/requirements/run/2": "# exact pin handled through openssl run_exports",
                "/outputs/2/requirements/host/0": "# Only required to produce all openssl variants.",
            },
        ),
    ],
)
def test_get_comments_table(file: str, expected: dict[str, str]) -> None:
    """
    Tests generating a table of comment locations
    """
    parser = load_recipe(file)
    assert parser.get_comments_table() == expected


@pytest.mark.parametrize(
    "file,ops,expected",
    [
        (
            "simple-recipe.yaml",
            [
                ("/package/name", "# Come on Jeffery"),
                ("/build/number", "# you can do it!"),
                ("/requirements/empty_field1", "Pave the way!"),
                ("/multi_level/list_1", "# Put your back into it!"),
                ("/multi_level/list_2/1", "# Tell us why"),
                ("/multi_level/list_2/2", " Show us how"),
                ("/multi_level/list_3/0", "# Look at where you came from"),
                ("/test_var_usage/foo", "Look at you now!"),
            ],
            "simple-recipe_test_add_comment.yaml",
        ),
    ],
)
def test_add_comment(file: str, ops: list[tuple[str, str]], expected: str) -> None:
    parser = load_recipe(file)
    for path, comment in ops:
        parser.add_comment(path, comment)
    assert parser.is_modified()
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/{expected}")


@pytest.mark.parametrize(
    "file,path,comment,exception",
    [
        ("simple-recipe.yaml", "/package/path/to/fake/value", "A comment", KeyError),
        ("simple-recipe.yaml", "/build/number", "[unix]", ValueError),
        ("simple-recipe.yaml", "/build/number", "", ValueError),
        ("simple-recipe.yaml", "/build/number", "    ", ValueError),
    ],
)
def test_add_comment_raises(file: str, path: str, comment: str, exception: BaseException) -> None:
    """
    Tests scenarios where `add_comment()` should raise an exception
    :param file: File to test against
    :param path: Path to add a comment
    :param comment: Comment to add
    :param exception: Exception expected to be raised
    """
    parser = load_recipe(file)
    with pytest.raises(exception):  # type: ignore
        parser.add_comment(path, comment)


## Patch and Search ##


def test_patch_schema_validation() -> None:
    """
    Tests edge cases that should trigger an exception on JSON patch schema validation. Valid schemas are inherently
    tested in the other patching tests.
    """
    parser = load_recipe("simple-recipe.yaml")
    # Invalid enum/unknown op
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "fakeop",
                "path": "/build/number",
                "value": 42,
            }
        )
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "",
                "path": "/build/number",
                "value": 42,
            }
        )
    # Patch has extra field(s)
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "replace",
                "path": "/build/number",
                "value": 42,
                "extra": "field",
            }
        )
    # Patch is missing required fields
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "path": "/build/number",
                "value": 42,
            }
        )
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "replace",
                "value": 42,
            }
        )
    # Patch is missing required fields, based on `op`
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "add",
                "path": "/build/number",
            }
        )
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "replace",
                "path": "/build/number",
            }
        )
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "move",
                "path": "/build/number",
            }
        )
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "copy",
                "path": "/build/number",
            }
        )
    with pytest.raises(JsonPatchValidationException):
        parser.patch(
            {
                "op": "test",
                "path": "/build/number",
            }
        )
    # Patch has invalid types in critical fields
    with pytest.raises(JsonPatchValidationException):
        parser.patch({"op": "move", "path": 42, "value": 42})
    with pytest.raises(JsonPatchValidationException):
        parser.patch({"op": "move", "path": "/build/number", "from": 42})


def test_patch_path_invalid() -> None:
    """
    Tests if `patch` returns false on all ops when the path is not found. Also checks if the tree has been modified.
    """
    parser = load_recipe("simple-recipe.yaml")

    # Passing an empty path fails at the JSON schema validation layer, so it applies to all patch functions.
    with pytest.raises(JsonPatchValidationException):
        assert not (
            parser.patch(
                {
                    "op": "test",
                    "path": "",
                    "value": 42,
                }
            )
        )

    # add
    assert not (
        parser.patch(
            {
                "op": "add",
                "path": "/package/path/to/fake/value",
                "value": 42,
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "add",
                "path": "/build/number/0",
                "value": 42,
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "add",
                "path": "/multi_level/list2/4",
                "value": 42,
            }
        )
    )
    # remove
    assert not (
        parser.patch(
            {
                "op": "remove",
                "path": "/package/path/to/fake/value",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "remove",
                "path": "/build/number/0",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "remove",
                "path": "/multi_level/list2/4",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "remove",
                "path": "/build/skip/true",
            }
        )
    )
    # replace
    assert not (
        parser.patch(
            {
                "op": "replace",
                "path": "/build/number/0",
                "value": 42,
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "replace",
                "path": "/multi_level/list2/4",
                "value": 42,
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "replace",
                "path": "/build/skip/true",
                "value": 42,
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "replace",
                "path": "/package/path/to/fake/value",
                "value": 42,
            }
        )
    )

    # move, `path` is invalid
    assert not (
        parser.patch(
            {
                "op": "move",
                "path": "/package/path/to/fake/value",
                "from": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "move",
                "path": "/build/number/0",
                "from": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "move",
                "path": "/multi_level/list2/4",
                "from": "/about/summary",
            }
        )
    )
    # move, `from` is invalid
    assert not (
        parser.patch(
            {
                "op": "move",
                "from": "/package/path/to/fake/value",
                "path": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "move",
                "from": "/build/number/0",
                "path": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "move",
                "from": "/multi_level/list2/4",
                "path": "/about/summary",
            }
        )
    )

    # copy, `path` is invalid
    assert not (
        parser.patch(
            {
                "op": "copy",
                "path": "/package/path/to/fake/value",
                "from": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "copy",
                "path": "/build/number/0",
                "from": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "copy",
                "path": "/multi_level/list2/4",
                "from": "/about/summary",
            }
        )
    )
    # copy, `from` is invalid
    assert not (
        parser.patch(
            {
                "op": "copy",
                "from": "/package/path/to/fake/value",
                "path": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "copy",
                "from": "/build/number/0",
                "path": "/about/summary",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "copy",
                "from": "/multi_level/list2/4",
                "path": "/about/summary",
            }
        )
    )

    # test
    assert not (
        parser.patch(
            {
                "op": "test",
                "path": "/package/path/to/fake/value",
                "value": 42,
            }
        )
    )

    assert not parser.is_modified()


def test_patch_test() -> None:
    """
    Tests the `test` patch op. The `test` op may be useful for other test assertions, so it is tested before the other
    patch operations.
    """
    parser = load_recipe("simple-recipe.yaml")

    # Test that values match, as expected
    assert parser.patch(
        {
            "op": "test",
            "path": "/build/number",
            "value": 0,
        }
    )
    assert parser.patch(
        {
            "op": "test",
            "path": "/build",
            "value": {
                "number": 0,
                "skip": True,
                "is_true": True,
            },
        }
    )
    assert parser.patch(
        {
            "op": "test",
            "path": "/requirements/host",
            "value": ["setuptools", "fakereq"],
        }
    )
    assert parser.patch(
        {
            "op": "test",
            "path": "/requirements/host/1",
            "value": "fakereq",
        }
    )
    assert parser.patch(
        {
            "op": "test",
            "path": "/about/description",
            "value": SIMPLE_DESCRIPTION,
        }
    )
    # Test that values do not match, as expected
    assert not (
        parser.patch(
            {
                "op": "test",
                "path": "/build/number",
                "value": 42,
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "test",
                "path": "/build",
                "value": {
                    "number": 42,
                    "skip": True,
                },
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "test",
                "path": "/requirements/host",
                "value": ["not_setuptools", "fakereq"],
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "test",
                "path": "/requirements/host/1",
                "value": "other_fake",
            }
        )
    )
    assert not (
        parser.patch(
            {
                "op": "test",
                "path": "/about/description",
                "value": "other_fake\nmultiline",
            }
        )
    )

    # Ensure that `test` does not modify the tree
    assert not parser.is_modified()


def test_patch_add() -> None:
    """
    Tests the `add` patch op.
    """
    parser = load_recipe("simple-recipe.yaml")

    # As per the RFC, `add` will not construct multiple-levels of non-existing structures. The containing
    # object(s)/list(s) must exist.
    assert not parser.patch(
        {
            "op": "add",
            "path": "/build/fake/meaning_of_life",
            "value": 42,
        }
    )
    # Similarly, appending to a list
    assert not parser.patch(
        {
            "op": "add",
            "path": "/requirements/empty_field1/-/blah",
            "value": 42,
        }
    )
    assert not parser.is_modified()

    # Add primitive values
    assert parser.patch(
        {
            "op": "add",
            "path": "/build/meaning_of_life",
            "value": 42,
        }
    )
    assert parser.patch(
        {
            "op": "add",
            "path": "/package/is_cool_name",
            "value": True,
        }
    )

    # Add to empty-key node
    assert parser.patch(
        {
            "op": "add",
            "path": "/requirements/empty_field2",
            "value": "Not so empty now",
        }
    )

    # Add list items
    assert parser.patch(
        {
            "op": "add",
            "path": "/multi_level/list_2/1",
            "value": "We got it all on UHF",
        }
    )
    assert parser.patch(
        {
            "op": "add",
            "path": "/multi_level/list_1/0",
            "value": "There's just one place to go for all your spatula needs!",
        }
    )
    assert parser.patch(
        {
            "op": "add",
            "path": "/multi_level/list_1/-",
            "value": "Spatula City!",
        }
    )

    # Add a complex value
    assert parser.patch(
        {
            "op": "add",
            "path": "/test_var_usage/Stanley",
            "value": [
                "Oh, Joel Miller, you've just found the marble in the oatmeal.",
                "You're a lucky, lucky, lucky little boy.",
                "'Cause you know why?",
                "You get to drink from... the FIRE HOOOOOSE!",
            ],
        }
    )

    # Add a top-level complex value
    assert parser.patch(
        {
            "op": "add",
            "path": "/U62",
            "value": {
                "George": ["How'd you like your own TV show?", "You're on"],
                "Stanley": ["Ok"],
            },
        }
    )

    # Add an object to a list
    assert parser.patch(
        {
            "op": "add",
            "path": "/multi_level/list_3/1",
            "value": {
                "George": {"role": "owner", "has_mop": False},
                "Stanley": {"role": "janitor", "has_mop": True},
            },
        }
    )

    # Edge case: adding a value to an existing key (non-list) actually replaces the value at that key, as per the RFC.
    assert parser.patch({"op": "add", "path": "/about/summary", "value": 62})

    # Add a value in a list with a comment
    assert parser.patch({"op": "add", "path": "/multi_level/list_1/1", "value": "ken"})
    assert parser.patch({"op": "add", "path": "/multi_level/list_1/3", "value": "barbie"})

    # Sanity check: validate all modifications
    assert parser.is_modified()
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_patch_add.yaml")


def test_patch_remove() -> None:
    """
    Tests the `remove` patch op.
    """
    parser = load_recipe("simple-recipe.yaml")

    # Remove primitive values
    assert parser.patch(
        {
            "op": "remove",
            "path": "/build/number",
        }
    )
    assert parser.patch(
        {
            "op": "remove",
            "path": "/package/name",
        }
    )

    # Remove empty-key node
    assert parser.patch(
        {
            "op": "remove",
            "path": "/requirements/empty_field2",
        }
    )

    # Remove list items
    assert parser.patch(
        {
            "op": "remove",
            "path": "/multi_level/list_2/0",
        }
    )
    # Ensure comments don't get erased
    assert parser.patch(
        {
            "op": "remove",
            "path": "/multi_level/list_1/1",
        }
    )

    # Remove a complex value
    assert parser.patch(
        {
            "op": "remove",
            "path": "/multi_level/list_3",
        }
    )

    # Remove a top-level complex value
    assert parser.patch(
        {
            "op": "remove",
            "path": "/about",
        }
    )

    # Sanity check: validate all modifications
    assert parser.is_modified()
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_patch_remove.yaml")


def test_patch_replace() -> None:
    """
    Tests the `replace` patch op.
    """
    parser = load_recipe("simple-recipe.yaml")
    # Patch an integer
    assert parser.patch(
        {
            "op": "replace",
            "path": "/build/number",
            "value": 42,
        }
    )
    # Patch a bool
    assert parser.patch(
        {
            "op": "replace",
            "path": "/build/is_true",
            "value": False,
        }
    )
    # Patch a string
    assert parser.patch(
        {
            "op": "replace",
            "path": "/about/license",
            "value": "MIT",
        }
    )
    # Patch an array element
    assert parser.patch(
        {
            "op": "replace",
            "path": "/requirements/run/0",
            "value": "cpython",
        }
    )
    # Patch an element to become an array
    assert parser.patch(
        {
            "op": "replace",
            "path": "/about/summary",
            "value": [
                "The Trial",
                "Never Ends",
                "Picard",
            ],
        }
    )
    # Patch a multiline string
    assert parser.patch(
        {
            "op": "replace",
            "path": "/about/description",
            "value": ("This is a PEP 561\ntype stub package\nfor the toml package."),
        }
    )

    # Hard mode: replace a string with an object containing multiple types in a complex data structure.
    assert parser.patch(
        {
            "op": "replace",
            "path": "/multi_level/list_2/1",
            "value": {"build": {"number": 42, "skip": True}},
        }
    )

    # Patch-in strings with quotes
    assert parser.patch(
        {
            "op": "replace",
            "path": "/multi_level/list_3/2",
            "value": "{{ compiler('c') }}",
        }
    )

    # Patch lists with comments
    assert parser.patch(
        {
            "op": "replace",
            "path": "/multi_level/list_1/0",
            "value": "ken",
        }
    )
    assert parser.patch(
        {
            "op": "replace",
            "path": "/multi_level/list_1/1",
            "value": "barbie",
        }
    )

    # Sanity check: validate all modifications
    assert parser.is_modified()
    # NOTE: That patches, as of writing, cannot preserve selectors
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_patch_replace.yaml")


def test_patch_move() -> None:
    """
    Tests the `move` patch op.
    """
    parser = load_recipe("simple-recipe.yaml")
    # No-op moves should not corrupt our modification state.
    assert parser.patch(
        {
            "op": "move",
            "path": "/build/number",
            "from": "/build/number",
        }
    )
    # Special failure case: trying to "add" to an illegal path while the "remove" path is still valid
    assert not parser.patch(
        {
            "op": "move",
            "path": "/build/number/0",
            "from": "/build/number",
        }
    )
    assert not parser.is_modified()
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe.yaml")

    # Simple move
    assert parser.patch(
        {
            "op": "move",
            "path": "/requirements/number",
            "from": "/build/number",
        }
    )

    # Moving list item to a new key (replaces existing value)
    assert parser.patch(
        {
            "op": "move",
            "path": "/build/is_true",
            "from": "/multi_level/list_3/0",
        }
    )

    # Moving list item to a different list
    assert parser.patch(
        {
            "op": "move",
            "path": "/requirements/host/-",
            "from": "/multi_level/list_1/1",
        }
    )

    # Moving a list entry to another list entry position
    assert parser.patch(
        {
            "op": "move",
            "path": "/multi_level/list_2/0",
            "from": "/multi_level/list_2/1",
        }
    )

    # Moving a compound type
    assert parser.patch(
        {
            "op": "move",
            "path": "/multi_level/bar",
            "from": "/test_var_usage/bar",
        }
    )

    # Sanity check: validate all modifications
    assert parser.is_modified()
    # NOTE: That patches, as of writing, cannot preserve selectors
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_patch_move.yaml")


def test_patch_copy() -> None:
    """
    Tests the `copy` patch op.
    """
    parser = load_recipe("simple-recipe.yaml")

    # Simple copy
    assert parser.patch(
        {
            "op": "copy",
            "path": "/requirements/number",
            "from": "/build/number",
        }
    )

    # Copying list item to a new key
    assert parser.patch(
        {
            "op": "copy",
            "path": "/build/is_true",
            "from": "/multi_level/list_3/0",
        }
    )

    # Copying list item to a different list
    assert parser.patch(
        {
            "op": "copy",
            "path": "/requirements/host/-",
            "from": "/multi_level/list_1/1",
        }
    )

    # Copying a list entry to another list entry position
    assert parser.patch(
        {
            "op": "copy",
            "path": "/multi_level/list_2/0",
            "from": "/multi_level/list_2/1",
        }
    )

    # Copying a compound type
    assert parser.patch(
        {
            "op": "copy",
            "path": "/multi_level/bar",
            "from": "/test_var_usage/bar",
        }
    )

    # Sanity check: validate all modifications
    assert parser.is_modified()
    # NOTE: That patches, as of writing, cannot preserve selectors
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_patch_copy.yaml")


def test_search() -> None:
    """
    Tests searching for values
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.search(r"fake") == ["/requirements/host/1"]
    assert parser.search(r"^0$") == ["/build/number"]
    assert parser.search(r"true") == ["/build/skip", "/build/is_true"]
    assert parser.search(r"py.*") == ["/requirements/run/0", "/about/description"]
    assert parser.search(r"py.*", True) == ["/build/skip", "/requirements/run/0", "/about/description"]
    assert not parser.is_modified()


def test_search_and_patch() -> None:
    """
    Tests searching for values and then patching them
    """
    parser = load_recipe("simple-recipe.yaml")
    assert parser.search_and_patch(r"py.*", {"op": "replace", "value": "conda"}, True)
    assert parser.render() == load_file(f"{TEST_FILES_PATH}/simple-recipe_test_search_and_patch.yaml")
    assert parser.is_modified()


def test_diff() -> None:
    """
    Tests diffing output function
    """
    parser = load_recipe("simple-recipe.yaml")
    # Ensure a lack of a diff works
    assert parser.diff() == ""

    assert parser.patch(
        {
            "op": "replace",
            "path": "/build/number",
            "value": 42,
        }
    )
    # Patch a bool
    assert parser.patch(
        {
            "op": "replace",
            "path": "/build/is_true",
            "value": False,
        }
    )
    # Patch a string
    assert parser.patch(
        {
            "op": "replace",
            "path": "/about/license",
            "value": "MIT",
        }
    )
    assert parser.diff() == (
        "--- original\n"
        "\n"
        "+++ current\n"
        "\n"
        "@@ -6,9 +6,9 @@\n"
        "\n"
        "   name: {{ name|lower }}  # [unix]\n"
        " \n"
        " build:\n"
        "-  number: 0\n"
        "+  number: 42\n"
        "   skip: true  # [py<37]\n"
        "-  is_true: true\n"
        "+  is_true: false\n"
        " \n"
        " # Comment above a top-level structure\n"
        " requirements:\n"
        "@@ -27,7 +27,7 @@\n"
        "\n"
        "     This is a PEP '561 type stub package for the toml package.\n"
        "     It can be used by type-checking tools like mypy, pyright,\n"
        "     pytype, PyCharm, etc. to check code that uses toml.\n"
        "-  license: Apache-2.0 AND MIT\n"
        "+  license: MIT\n"
        " \n"
        " multi_level:\n"
        "   list_1:"
    )
