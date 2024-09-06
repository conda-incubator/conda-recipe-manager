# `conda-recipe-manager`

## Overview
This `README` acts as a brief technical overview of the components that make up the `conda-recipe-manager` library.

## Modules

### `commands`
This module provides a set of command line interfaces that can be used to test-out and work with the primary features
of the library without developing custom code.

Some of these CLIs are very demo-focused and others provide significant value, like the `convert` command.
All commands defined are subcommands of the `conda-recipe-manager` command. The top-level command has also been
abbreviated to `crm` for your typing convenience.

### `grapher` (WIP)
This module provides tools that are capable of plotting and understanding how recipe dependencies are related to each
other.

### `licenses` (WIP)
This module provides license file utilities.

### `parser`
This module provides various tools to parse common `conda` recipe file formats and other `conda-build` constructs.
The primary class for reading recipe files is called the `RecipeReader` while editing capabilities can be found in the
`RecipeParser`. For additional recipe management features, seek out the derivatives of these two base classes.


### `scanner` (WIP)
This module provides tools for _scanning_ files and other feedstock/recipe artifacts. Unlike the parsers, full
comprehension of the file(s) is not guaranteed.
