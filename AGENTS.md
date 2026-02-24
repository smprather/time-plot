# AGENTS.md

Guidance for coding agents working in this repository.

## Scope

- Applies to the entire repository unless a deeper `AGENTS.md` overrides it.

## Project Overview

- Project: `time-plot`
- Script name: `time_plot`
- Purpose: plot time-series data (non-calendar time on x-axis) using embedded `Dygraphs` JavaScript in generated HTML.
- Runtime: Python (`>=3.14`) managed with `uv`

## Terminology

- `Dygraphs` (plural): the browser plotting library used in generated HTML.
- `dygraph` / `DyGraph`: Python package names in `pyproject.toml` / environment. Do not assume this is the browser plotting library.
- `data set`: one named y-series over time.
- `y-axis type`: defined as the tuple `(y_label, y_unit)`.

## Current Implemented Features

- Plugin-based file parsing with deterministic discovery (sorted by plugin package/file name).
- Seed parser plugin:
  - Plugin ID: `voltage-vs-time-csv`
  - Package directory: `plugins/voltage_vs_time_csv`
- Example data generation:
  - `sample_data/sine.csv`
  - `sample_data/cosine.csv`
  - CLI command: `sample-files`
  - Script: `scripts/generate_example_data.py`
- CLI positional source parsing:
  - files
  - named files (`name:path`)
  - expressions (`expr[...]` and `name:expr[...]`)
  - default names `fN` based on argument position
- Multi-file alignment:
  - deterministic common x-grid
  - smallest positive source `dx` used as global timestep
  - linear interpolation
  - no extrapolation outside a source range (`NaN`)
  - strict increasing x validation
- Expression evaluation (safe AST):
  - operators: `+`, `-`, `*`, `/`
  - functions: `sin()`, `cos()`, `ddt()`
  - chained expressions
  - circular reference detection
  - unknown reference detection
- Plotting:
  - multiple traces
  - dual y-axis support (up to two y-axis data types)
  - SI unit auto-scaling for display
  - vendored `Dygraphs` JS/CSS embedded inline for offline HTML; CDN `<script>`/`<link>` tags used when vendor files are missing
  - client-side SVG fallback: a JS function renders an SVG chart when `window.Dygraph` is not available (still requires a JS-capable browser)

## Known Limitations (Current)

- Expression function set is intentionally small (`sin`, `cos`, `ddt` only).
- Expression unit handling is pragmatic:
  - `+/-` require matching units
  - `*` and `/` build composed unit strings (for example `v/s`, `v*v`)
  - no symbolic simplification
- Internal storage does not yet implement the optimization “store only min x + global timestep” for every data set.
- CLI/integration coverage is focused and not exhaustive.

## MVP Scope (Next Work)

- Extend expression function set as needed (`abs`, `sqrt`, filters, etc.).
- Improve expression unit semantics/simplification.
- Add more parser plugins (including a second y-axis type to exercise dual-axis behavior end-to-end).
- Strengthen CLI/integration tests for error cases and mixed input scenarios.

## Project Goals (Target Behavior)

- Read x, y data from multiple input sources.
- The x-axis data is time as zero-based "instants"; it is never calendar date-based.
  - Always label the x-axis as `Time (<units>)`.
- The source of x, y data should be implemented as a plugin so users can add new formats.
- Support up to two different y-axis types in a single plot.
- Support generated data sets (expressions) that are functions of other data sets.

## Seed Format Plugin (Template and Dev Plugin)

- Format name: `Voltage vs. Time CSV`
- Plugin ID: `voltage-vs-time-csv`
- Plugin package directory: `plugins/voltage_vs_time_csv`
- Base format: CSV with header names `time(<unit>)` and `voltage(<unit>)`
- Units are stored in header parentheticals (for example `time(ns)`)
- Recognition rule:
  - filename must end in `.csv`
  - first line must have column names `time(...)` and `voltage(...)`
  - ignore parenthetical units when checking support
  - Example recognized header: `time(ns),voltage(v)`
- y-axis label returned by the plugin: `Voltage`

## Example Data Utility Requirements

- Used for development and test writing.
- Write files to `sample_data/`.
- CSV headers must be `time(ns),voltage(mv)`.
- Required files:
  - `sine.csv`
    - 1000 points spanning `1.0` microsecond
    - 2 cycles of sine wave
    - amplitude `1 V` (stored as `mV`)
  - `cosine.csv`
    - 800 points spanning `2.0` microseconds
    - 3 cycles of cosine wave
    - amplitude `2 V` (stored as `mV`)

## Parser Plugin Rules

- A parser plugin is a Python package auto-discovered and imported by the main program.
- Plugins are stored in a `plugins/` directory located beside the executable script.
- A plugin must provide an identification function that checks support for a file.
- Plugin identification is attempted in deterministic order.
  - Current rule: sorted by plugin package/file name.
- The first matching plugin is used.
- If a plugin supports a file, it must return data equivalent to:
  - acknowledgement of support (implicitly via successful parse)
  - y base unit with no SI prefix (trusted convention)
  - x values converted to seconds
  - `float64` numpy arrays for x and y in base units
  - literal y-axis label

## CLI Rules

- Positional arguments may refer to:
  1. File paths
  1. Expressions (`expr[...]`)
- A file or expression may be named with `<name>:` prefix:
  - Example: `data1:/foo/bar.csv`
  - Example: `total:expr[f1+f2]`
- Unnamed sources are auto-named `fN` where `N` is the positional argument number (starting at `1`).
  - Example: `time_plot foo.csv bar.csv`
    - `foo.csv` is `f1`
    - `bar.csv` is `f2`
- Names for any data set (file or expression) share one namespace.
  - Duplicate names are errors.
- Expression references use data set names.
  - For predictable references, use valid Python identifiers in names.
  - Auto-names (`fN`) are always valid identifiers.
- Shell usage:
  - Quote expression arguments to avoid shell parsing issues.
  - Example: `time_plot foo.csv 'total:expr[f1+f1]'`

## Data Model Conventions

- x-axis is always time and always stored internally in seconds.
- x-axis label is always `Time (<display units>)`.
- y-axis type is `(y_label, y_unit)`.
- At most two distinct y-axis types may be present in one plot.
- Legend names may collide.
  - Plot output may deduplicate labels for display (for example `Voltage [2]`).

## Data Processing Rules

- x-axis is the superset of all supplied file-backed x-axis data.
- x-axis data must be strictly increasing (no repeats, no decreases).
- x-axis need not have homogeneous timesteps in source files.
- Global x-axis timestep is the smallest positive `delta x` across file-backed sources.
- All sources are aligned to a common x-grid by linear interpolation.
- No extrapolation outside a source’s x-range.
  - Missing values outside range are `NaN`.
- Global x-grid endpoint behavior:
  - include the exact global `x_max` even if it is not an integer multiple of the global timestep from `x_min`.
- A global x-axis timestep should be stored and used.
  - Current implementation stores `x_timestep_seconds` in the aligned plot model.
- Expressions may refer to file-backed data sets and other expressions.
- Names are assigned to all data sets before expression evaluation.
- Circular expression references are errors.
- Expression results are computed only where all referenced inputs are available.
  - Missing inputs propagate to `NaN`.

## Expression Semantics

- Supported operators (current minimum set): `+`, `-`, `*`, `/`
- Supported functions (current minimum set): `sin()`, `cos()`, `ddt()`
- `ddt()` rule:
  - derivative is computed by finite difference on aligned x-grid
  - first timestep value equals the second timestep value (when available)
- Unit rules (current implementation):
  - `+/-`: units must match
  - `*`: composed unit string (for example `v*v`)
  - `/`: composed unit string (for example `v/s`)
  - `sin/cos`: unitless result (`1`)
  - `ddt(x)`: unit becomes `<unit>/s`
- Expressions are currently intended to be used with at least one file-backed input.

## Plotting Rules

- When two y-axis types are present, use `Dygraphs` dual y-axis support.
- Legend naming precedence (highest to lowest):
  1. CLI name (`<name>:`)
  1. Parser plugin-provided y label
  1. Basename of the input file without extension
  1. Expression text with spaces removed
- SI display scaling must be auto-selected for readability.
  - Current heuristic target:
    - prefer max magnitude in a readable range
    - bias toward values near `1`
    - examples: `1e-6 s -> us`, `~1 v -> v`

## Next Implementation Priorities

- Expand expression function set and documentation.
- Improve unit simplification/validation for expressions.
- Add a second parser/type to exercise dual-y plots in realistic CLI flows.
- Add stronger end-to-end CLI tests for mixed files + expressions + error conditions.
- Consider implementing compact per-dataset x storage (`x_min + global dt`) if memory/performance becomes relevant.

## Setup

- Required tools: `uv`, Python `3.14+`
- Sync dependencies: `uv sync --group dev`

## Common Commands

- CLI (preferred): `uv run time_plot ...`
- Dev fallback entrypoint: `uv run python main.py ...`
- Generate example files: `uv run time_plot sample-files`
- Run tests: `uv run pytest`
- Add dependency: `uv add <package>`
- Add dev dependency: `uv add --dev <package>`

## Validation Checklist

- Run focused tests for changed modules first.
- Minimum useful commands:
  - `uv run pytest -q`
  - `uv run time_plot sample-files`
  - `uv run time_plot plot sample_data/sine.csv`
  - `uv run time_plot plot sample_data/sine.csv 'sum:expr[f1+f1]' 'r:expr[ddt(sum)]'`
- If skipping validation, state why in handoff.

## Repository Structure

- `main.py`: dev entry point
- `pyproject.toml`: project metadata and dependencies
- `uv.lock`: locked dependency versions
- `time_plot/`: application package
- `plugins/`: parser plugins
- `vendor/`: vendored Dygraphs JS/CSS for offline HTML output
- `sample_data/`: generated example CSV files
- `scripts/`: developer utility scripts
- `tests/`: automated tests
- `README.md`: project documentation

## Coding Standards

- Prefer clear names over clever abstractions.
- Update docs/comments when behavior changes.
- Keep Python code compatible with the version declared in `pyproject.toml`.
- Always use `pathlib` when possible.

## Testing Expectations

- Add or update tests for behavior changes when feasible.
- Prefer small focused tests first, then integration-style checks.
- If tests are skipped or unavailable, note that in the handoff.

## Change Safety

- Check for existing local changes before editing shared files.

## PR / Handoff Notes

- Summarize what changed and why.
- Note follow-up work, risks, or assumptions.
- Include commands run for validation and outcomes.

## Agent-Specific Instructions

- Prefer `uv` for dependency and command execution.
- If introducing tests, add test tooling to dev dependencies in `pyproject.toml`.
- `uv run pytest` should work against live workspace code after `uv sync --group dev` (editable install support is implemented in `local_build_backend.py`).

## Tech Stack

- Python >= 3.14
- `Dygraphs` (embedded JS assets in generated HTML)
- Click CLI
- Pytest
- Astral Ruff
- Astral Ty
