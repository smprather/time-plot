# AGENTS.md

Guidance for coding agents working in this repository.

## Scope

- Applies to the entire repository unless a deeper `AGENTS.md` overrides it.

## Project Overview

- Project: `time-plot`
- Script name: time_plot
- Purpose: plot time-series data using `DyGraph` (per `pyproject.toml`)
- Runtime: Python (`>=3.14`) managed with `uv`

## Project Goals

- Read x, y data from multiple input sources.
- The x axis data is time as zero-based "instants". In other words, it's not ever calendar date-based.
  - Always label the x axis as "Time (units)". Example: "Time (ns)"
- The source of x, y data should be implemented as a plugin to this package so that anyone can write their own data format parser.
- Support for up to two different y axis data types.
- Support for generated data-sets (expressions) that are a function of other data-sets.

## Seed Format Plugin

- Create an example parser plugin.
- It will be used for tool development, and as a template for the user to create plugins.
- The name of this format is "Voltage vs. Time CSV".
- The name of the plugin is "voltage-vs-time-csv".
- The base format is that of a CSV file with header names: time(unit) and voltage(unit).
- The data units should be in the header name parenthetical. Example: time(ns)
- If the recognition function sees that the filename ends in .csv, and the first line of the file is "time(ns),voltage(v)", then it will claim itself as the supporter.
  - Ignore the units in the parentheticals when checking for support.
- The y axis data name is "Voltage".

## Create a utility script to generate example data files.

- Used for script development and test writing.
- Write the files to the sample_data directory.
- Store the data in csv files with time(ns) and voltage(mv) as the column headers.
- File 1: sine.csv
  - 1000 points spanning 1.0 microsecond
  - Two cycles of sine wave with an amplitude of 1v.
- File 2: cosine.csv
  - 800 points spanning 2.0 microsecond
  - Three cycles of cosine wave with an amplitude of 2v.

## Parser Plugin Rules

- A parser plugin is a python package that is auto-recognized and imported by main.
- Plugins are stored in a plugins directory located in the directory that contains the executable script.
- A plugin must have an identification function that is called to query if the data to be plotted is of the type supported by the plugin.
- The main software calls the identification functions of each plugin in a deterministic order.
  - The coding agent can choose the order, so long as it is repeatable.
- The first plugin that identifies itself as a supporter of the specified file type, is used to parse the data.
- If a plugin supports the data type, it returns:
  - Acknowledgement that the plugin supports this data format.
  - The base unit for the y data. Must not include any SI scaling prefixes. Since there's no reliable way to error check that no SI
    scaling prefixes are in the unit, we must assume that whatever is given is a correct base unit with no SI prefix.
  - X axis data must always be converted to seconds.
  - The list of X, Y points as float64 numpy arrays in terms of the base unit. Ie, no SI scaling prefix should be used.
    Example: For volts, the data must be returned in terms of volts even if the data-file contains millivolts.
  - The literal name to use for the y axis.

## CLI Rules

- Positional arguments.
  - Can refer to
    1. File paths.
    1. Expressions composed of other data-sets.
  - A file can be given a name by preceding the file path with <name>:
    - Example data1:/foo/bar.csv
  - An argument of the format expr[...] is an expression of other data-sets
    - It may also be preceded with a <name>: identifier
  - Any data-set not explicitly given a name will be given the default name of fN where N is the position of the argument starting
    with 1.
    Example: time_plot foo.csv bar.csv
    foo.csv is auto-named f1
    bar.csv is auto-named f2
  - Expressions support a basic set of mathematical operators +, -, \*, /. And a basic set of functions, like sin(), cos(), ddt(), etc.
    Example: time_plot foo.csv bar.csv total:expr[f1+f2]
    - Note for implementing time derivative ddt(), Make the value for the first timestep equal to the value of the second timestep.

## Data Processing Rules

- The input sources can have, at most, two different y-axis types.
- The x-axis is the superset of all the supplied x-axis data.
- Error check for x-axis data that is non-monotonic, or decreasing.
- X axis data need not be homogenous timesteps.
- The smallest timestep (delta x) among all non-computed data sources becomes the timestep for all of the data-sources.
  - Insert linearly interpolated x,y points so that all data sources will have the same set of x axis values.
  - A global x-axis timestep should be stored and used.
  - Each data-set should only store the minimum value of its x axis data.
  - This guarantees that all x time points will match exactly across data-sets.
- Each data-set can have a different number of y points.
- Expressions may refer to other named expressions (including auto-named expressions).
- Assign names to all the data-sets first.
  - So that expressions need not have all data-sets named prior to the expression definition.
  - Detect circular reference expressions.
    Example: This is an error: foo:expr[foo]
    Example: This is an error: foo:expr[bar] bar:expr[foo]
- When calculating expression data, only compute values for which y data is available for every referenced data-set.

## Plotting Rules

- When two types of data are supplied, use DyGraph's dual y-axis support.
- The legend name for a data-set is determined in order of precedence.
  Highest to lowest:
  1. Name given on the command line using the <name>: syntax.
  1. Name returned by the parser plugin.
  1. Basename of the data filename, not including the file extension.
  1. For an expression, the text of the expression with spaces removed.
- The level of SI scaling units for plotting must be auto-selected.
  - Use "best human readability" guidelines.

## Setup

- Required tools: `uv`, Python `3.14+`
- Sync dependencies: `uv sync`

## Common Commands

- Run app: `uv run python main.py`
- Run tests: `uv run pytest` (add `pytest` first if not present)
- Add dependency: `uv add <package>`
- Add dev dependency: `uv add --dev <package>`

## Repository Structure

- `main.py`: current entry point
- `pyproject.toml`: project metadata and dependencies
- `uv.lock`: locked dependency versions
- `README.md`: project documentation (currently minimal)

## Coding Standards

- Prefer clear names over clever abstractions.
- Update docs/comments when behavior changes.
- Keep Python code compatible with the version declared in `pyproject.toml`.
- Always use Pathlib when possible.

## Testing Expectations

- Add or update tests for behavior changes when feasible.
- Prefer small focused tests first.
- If tests are skipped or unavailable, note that in the handoff.

## Change Safety

- Check for existing local changes before editing shared files.

## PR / Handoff Notes

- Summarize what changed and why.
- Note follow-up work, risks, or assumptions.
- Include commands run for validation and their outcomes.

## Agent-Specific Instructions

- Prefer `uv` for dependency and command execution.
- If introducing tests, add test tooling to dev dependencies in `pyproject.toml`.

## Tech Stack

- Python >= 3.14
- DyGraph
- Click CLI
- Pytest
- Astral Ruff
- Astral Ty
