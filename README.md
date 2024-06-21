# conda-recipe-manager

## Table of Contents
<!-- TOC -->
# Overview
A project for libraries and automated tools that manage and manipulate conda recipe files.

This project started out as a recipe parser library in Anaconda's
[percy](https://github.com/anaconda-distribution/percy/tree/main) project.

# Getting Started

## General Installation

### Install into your current environment
```sh
make install
```

### Install into a custom environment
```sh
make environment
conda activate conda-recipe-manager
```

# Developer Notes
```sh
make dev
conda activate conda-recipe-manager
```
The `dev` recipe will configure a `conda` environment named `conda-recipe-manager` with
development tools installed.

`pre-commit` is automatically installed and configured for you to run a number
of automated checks on each commit.

**NOTE:** As of writing, only a handful of files are checked by the linter and
`pre-commit`. **ANY NEW FILES** should be added to these checks.

### Running pre-commit checks
The provided `Makefile` also provides a handful of convenience recipes for
running all or part of the `pre-commit` automations:
1. `make test`: Runs all the unit tests
1. `make test-cov`: Reports the current test coverage percentage and indicates
   which lines are currently untested.
1. `make lint`: Runs our `pylint` configuration, based on Google's Python
   standards.
1. `make format`: Automatically formats code
1. `make analyze`: Runs the static analyzer, `mypy`.
1. `make pre-commit`: Runs all the `pre-commit` checks

## Release process
1. Update `CHANGELOG.md`
1. Update the version number in `pyproject.toml`
1. Ensure `environment.yaml` is up to date with the latest dependencies
1. Create a new release on GitHub with a version tag.
1. Manage the conda-forge feedstock, as per [this doc](https://conda-forge.org/docs/maintainer/adding_pkgs/)
