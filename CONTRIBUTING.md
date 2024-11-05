# Contributing
Before contributing to this project, please check to see if a similar or identical GitHub issue is already open.
If no such issue applies, please file one so we may openly discuss the requested changes. This process aims to prevent
duplicated work and to reduce wasted time on work that may already be underway.

We welcome all contribution types. However, for code contributions, please follow the guide below to ensure your
contributions follow our expectations for engineering excellence.

The maintainers of this project manage a project board
[here](https://github.com/orgs/conda-incubator/projects/11/views/1?groupedBy%5BcolumnId%5D=Milestone). When an issue is
filed, we aim to quickly organize it into this board.

Please note we follow the `conda` organization's
Code of Conduct](https://github.com/conda/governance/blob/main/CODE_OF_CONDUCT.md).

## Code PR Requirements
The following is a list of requirements for code contributions. Most rules (if not all) are enforced with automated
code checks.
- A PR that does not pass our CI workflows, will not be accepted. All automated code checks can be run locally.
    - Our development environment (created with `make dev`) will automatically install and configure `pre-commit` to
      enforce our code checks.
- Unless otherwise approved/discussed, contributions must be done in Python with a minimum target version of 3.11
- Code must be automatically formatted per our rule set (enforced by `isort` and `black`)
- Code must comply to our linting rule set (enforced by `pylint`)
- Code must comply to our static analyzer rule set (enforced by `mypy`)
- Code must be documented. Modules, functions, classes, and files must use
  [reST](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html) formatting so that our automated API
  documentation system can publish API docs for our users.
  - Please aim to capture the "why" of a problem in in-code comments, especially if there is a lot of nuance.
- If there is work that needs to be completed at a latter date, file a new issue, tag it to the existing, and leave a
  `TODO` comment (where appropriate) explaining the situation.
