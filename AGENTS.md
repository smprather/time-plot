# AGENTS.md

Guidance for coding agents working in this repository.

## Scope

- Applies to the entire repository unless a deeper `AGENTS.md` overrides it.

## Project Overview

- Project: `time-plot`
- Purpose: plot generic time-series data using `dygraph` (per `pyproject.toml`)
- Runtime: Python (`>=3.14`) managed with `uv`

## Project Goals

- Read x, y data from multiple input sources.
- The x axis data is time as zero-based "instants", ie, not date-based.
- Represent x as a floating-point value, not a DateTime, or similar, calendar based data-type.
- The source of x, y data should be implemented as a plugin to this package so that anyone can write their own data parser.
- The parser plugin works like this:
  - A python package that is auto-recognized and imported by main.
  - Stored in a plugins directory in the base directory of the repository.
  - Must have an identification function that is called to query if the data to be plotted is of the type supported by the plugin.
  - The main software calls the identification functions of each plugin in arbitrary order.
  - The first plugin that identifies itself as a supporter of the specified file type, is used to parse the data.
  - If a plugin supports the data type, it returns:
    - Acknoledgement that the plugin supports the data.
    - The units for the x and y data. The x unit must be a time unit - m (minutes), s (seconds), ms, ms, us, ns, fs, etc.
    - The list of X, Y points as float64 numpy arrays
    - The literal names to use for the x and y axis. This may differ from column headers in the format.
- Create a sample x, y file format as the development plugin
  - The name of this format is "Voltage vs. Time CSV".
  - The name of the plugin is "voltage-time-csv".
  - Time should be in the header parenthetical.
  - Make it a 1000 time-point (1us total) sine wave with amplitude of 1
  - The y unit is millivolts (mv)
  - Store the data in a csv file with time and voltage as the column headers (time,voltage)
  - If the recognizer sees that the first line of the file is "time(ns),voltage", then it will claim itself as the supporter.
  - The data names for plotting are "Voltage" and "Time".
- Just to get started, plot the x, y data with your best guesses. We'll add more over time.

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

- Do not make unrelated refactors unless requested.
- Avoid destructive commands (`rm`, `git reset --hard`, etc.) unless explicitly requested.
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
- Astral Ruff
- Astral Ty
