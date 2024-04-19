# Scripts

## Overview

This directory contains 1-off development scripts related to this project.

They should not be packaged to be run by a user/consumer of this project.

# parse_ci_output.py

Utility script that reads the directory of log files provided by GitHub's CI infrastructure. The script then
parses-out the JSON output from the integration tests and aggregates the statistics into an accumulative
JSON structure.

## Usage:
```sh
usage: parse_ci_output.py [-h] [-v] dir
```
Where `-v` enables the `verbose` report, including the fully-parsed JSON found in all of the logs and
`dir` is the directory containing the log files from GitHub.

# randomly_select_recipes.py

Given a list of feedstock repositories owned by a GitHub organization, randomly select `NUM_RECIPES` number of recipe
files to dump into `OUT_DIR`

## Dependencies
- `requests`
- Some manual work with `gh` to produce the input file

## Usage:
```sh
./randomly_select_recipes.py [-e EXCLUDE_FILE] FILE NUM_RECIPES OUT_DIR
```
Where `-e EXCLUDE_FILE` is a list of repository names (1 line per repo name) to ignore when randomly selecting
recipes from the other list. This is useful for generating multiple sets of non-overlapping repository files.

For `conda-forge`, the input file used by this script was generated with:
```sh
gh repo list conda-forge -L 20000 > conda-forge-list.out
```
