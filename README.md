[commit-checks-badge]: https://github.com/conda-incubator/conda-recipe-manager/actions/workflows/commit_checks.yaml/badge.svg?branch=main
[integration-tests-badge]: https://github.com/conda-incubator/conda-recipe-manager/actions/workflows/integration_tests.yaml/badge.svg?branch=main
[release-badge]: https://img.shields.io/github/v/release/conda-incubator/conda-recipe-manager?logo=github


# conda-recipe-manager

[![Commit Checks][commit-checks-badge]](https://github.com/conda-incubator/conda-recipe-manager/actions/workflows/commit_checks.yaml)
[![Integration Tests][integration-tests-badge]](https://github.com/conda-incubator/conda-recipe-manager/actions/workflows/integration_tests.yaml)
[![GitHub Release][release-badge]](https://github.com/conda-incubator/conda-recipe-manager/releases)

## Table of Contents
<!-- TOC -->

- [conda-recipe-manager](#conda-recipe-manager)
    - [Table of Contents](#table-of-contents)
- [Overview](#overview)
    - [History](#history)
- [Getting Started](#getting-started)
    - [General Installation](#general-installation)
        - [Install into your current environment](#install-into-your-current-environment)
        - [Install into a custom environment](#install-into-a-custom-environment)
- [Developer Notes](#developer-notes)
        - [Running pre-commit checks](#running-pre-commit-checks)
    - [Release process](#release-process)
- [Special Thanks](#special-thanks)

<!-- /TOC -->
# Overview
Conda Recipe Manager (CRM) is a library and tool set capable of parsing Conda recipe files. It is intended to be
used by package builders and developers to automate the generation and editing of Conda recipe files.

Currently only recipe files in the V0 format are supported, but there is some on-going work to add full support for
V1-formatted files.

Library documentation can be found [here](https://conda-incubator.github.io/conda-recipe-manager/index.html).

## History
This project started out as a recipe parsing library in Anaconda's
[percy](https://github.com/anaconda-distribution/percy) project.

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
1. Update the version number in `pyproject.toml`, `docs/conf.py`, and `recipe/meta.yaml`
1. Ensure `environment.yaml` is up to date with the latest dependencies
1. Create a new release on GitHub with a version tag.
1. Manage the conda-forge feedstock, as per [this doc](https://conda-forge.org/docs/maintainer/adding_pkgs/)

# Special Thanks
- @cbouss for his work on the [Percy project](https://github.com/anaconda/percy) that originally inspired the recipe parser.
- @akabanovs for his work and experimentation on package dependency graph building.
- @JeanChristopheMorinPerso for his PR review contributions when this project was a part of `Percy` and answering questions about the `conda` file formats.
