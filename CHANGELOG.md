# Changelog
Note: version releases in the 0.x.y range may introduce breaking changes.


## 0.2.1
Minor bug fixes and documentation improvements. Conversion compatibility with Bioconda recipe has improved significantly.

Includes many previously missing recipe transformations.

### Pull Requests
- Fixes integration tests from rattler-build 0.18.0 update (#76)
- Adds common environment settings (#75)
- Adds demo day intro slidedeck to CRM (#73)
- Upgrades basic quoted multiline strings (#72)
- Adds missing transforms for "git source" fields (#71)
- pip check improvements, more missing transforms, and some spelling enhancements (#70)
- Multiline summary fix issue 44 (#68)
- Preprocessor: Replace dot with bar functions (#67)
- Corrects using hash_type as a JINJA variable for the sha256 key (#66)
- Adds script_env support (#65)
- Adds missing build transforms (#62)
- Some minor improvements (#61)

## 0.2.0
Major improvements from `0.1.0`, mostly dealing with compatibility with `rattler-build`.
This marks the first actual release of the project, but still consider this work to be experimental
and continually changing.

## 0.1.0
Migrates parser from [percy](https://github.com/anaconda-distribution/percy/tree/main)
, ,
