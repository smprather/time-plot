# Architecture

Project specification and design documentation for `time-plot`.

## Project Overview

- Project: `time-plot`
- Script name: `time_plot`
- Purpose: plot time-series data (non-calendar time on x-axis) using embedded `uPlot` JavaScript in generated HTML.
- Runtime: Python (`>=3.14`) managed with `uv`

## Tech Stack

- Python >= 3.14
- `uPlot` via `uplot-python` (embedded JS assets in generated HTML)
- Click CLI
- Pytest
- Astral Ruff
- Astral Ty

## Repository Structure

- `main.py`: dev entry point
- `pyproject.toml`: project metadata and dependencies
- `uv.lock`: locked dependency versions
- `time_plot/`: application package
- `plugins/`: parser plugins
- `sample_data/`: generated example CSV files
- `scripts/`: developer utility scripts
- `tests/`: automated tests
- `doc/`: project documentation
- `README.md`: project documentation

## Terminology

- `uPlot`: the browser plotting library used in generated HTML. JS/CSS assets are sourced from the `uplot-python` pip package.
- `uplot-python`: Python package providing uPlot static assets. We use only the bundled JS/CSS, not the Python plotting API.
- `data set`: one named y-series over time.
- `y-axis type`: defined by `y_unit` alone. The label is cosmetic; only the unit determines axis grouping.

## Project Goals (Target Behavior)

- Read x, y data from multiple input sources.
- The x-axis data is time as zero-based "instants"; it is never calendar date-based.
  - Always label the x-axis as `Time (<units>)`.
- The source of x, y data should be implemented as a plugin so users can add new formats.
- Support up to two different y-axis types in a single plot.
- Support generated data sets (expressions) that are functions of other data sets.

## Current Implemented Features

- Plugin-based file parsing with deterministic discovery (sorted by plugin package/file name).
- Seed parser plugin:
  - Plugin ID: `voltage-vs-time-csv`
  - Package directory: `plugins/voltage_vs_time_csv`
- SPICE PWL parser plugin:
  - Plugin ID: `spice-pwl`
  - Package directory: `plugins/spice_pwl`
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
  - functions: `average()`, `rms()`, `abs()`, `ddt()`
  - chained expressions
  - circular reference detection
  - unknown reference detection
- Plotting:
  - multiple traces
  - dual y-axis support (up to two y-axis data types)
  - SI unit auto-scaling for display
  - `uPlot` JS/CSS inlined from `uplot-python` package for self-contained offline HTML
  - mousewheel zoom plugin (`uPlot.mousewheel.js`) included for scroll-to-zoom

## Known Limitations (Current)

- Expression function set is intentionally small (`average`, `rms`, `abs`, `ddt` only).
- Expression unit handling is pragmatic:
  - `+/-` require matching units
  - `*` and `/` build composed unit strings (for example `v/s`, `v*v`)
  - no symbolic simplification
- Internal storage does not yet implement the optimization "store only min x + global timestep" for every data set.
- CLI/integration coverage is focused and not exhaustive.

## MVP Scope (Next Work)

- Extend expression function set as needed (`sqrt`, filters, etc.).
  - sqrt() should be next. Don't do any other functions until requested.
- Improve expression unit semantics/simplification.
- Add more parser plugins (including a second y-axis type to exercise dual-axis behavior end-to-end).
- Strengthen CLI/integration tests for error cases and mixed input scenarios.

## Next Implementation Priorities

- Expand expression function set and documentation.
- Improve unit simplification/validation for expressions.
- Add a second parser/type to exercise dual-y plots in realistic CLI flows.
- Add stronger end-to-end CLI tests for mixed files + expressions + error conditions.
- Consider implementing compact per-dataset x storage (`x_min + global dt`) if memory/performance becomes relevant.

## Parser Plugin Rules

- A parser plugin is a Python package auto-discovered and imported by the main program.
- Plugins are stored in a `plugins/` directory located beside the executable script.
- A plugin must provide an identification function that checks support for a file.
- Plugin identification is attempted in deterministic order.
  - Current rule: sorted by plugin package/file name.
- The first matching plugin is used.
- `parse()` receives `(file_path, options)` where `options` is `dict[str, str]` from the CLI `--parser-options` flag, and returns `list[SeriesData]`. Single-dataset plugins return a one-element list.
- If a plugin supports a file, each `SeriesData` must provide:
  - `name`: a per-dataset identifier (required). For multi-series returns, used to build the dataset key (e.g., `f1_voltage` instead of `f1_1`) and as the default legend name.
  - `y_unit`: short unit code with no SI prefix (e.g., `"v"`, `"i"`) — used for axis grouping and SI scaling.
  - `y_unit_label`: long-form unit name (e.g., `"Voltage"`, `"Current"`) — used for y-axis display labels.
  - x values converted to seconds
  - `float64` numpy arrays for x and y in base units
  - literal y-axis label

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
- y-axis label returned by the plugin is the name of the file without the .csv extension.

## SPICE PWL Plugin

- Format name: `SPICE PWL`
- Plugin ID: `spice-pwl`
- Plugin package directory: `plugins/spice_pwl`
- Parses SPICE netlists containing PWL (piecewise-linear) voltage or current sources.
- Recognition rule:
  - First non-comment (`*`), non-empty line must start with `i` or `v` (case-insensitive).
  - That line, whitespace-split, must contain `pwl` (substring match) at position index >= 3.
- Line continuations: lines starting with `+` are appended to the previous logical line before parsing.
- Source type determines y-unit: `v` prefix → y_unit `v`, `i` prefix → y_unit `i`.
- PWL values are time-value pairs with SPICE numeric suffixes (`n`=1e-9, `m`=1e-3, `u`=1e-6, `k`=1e3, `meg`=1e6, etc.).
- Time values are converted to seconds; y values are stored in base units.
- Each PWL source in the file produces one `SeriesData` with `name` set to the SPICE source name (e.g., `i1`).

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
- y-axis type is determined by `y_unit` alone.
- At most two distinct y-axis units may be present in one plot.
- Legend names may collide.
  - Plot output may deduplicate labels for display (for example `Voltage [2]`).

## Data Processing Rules

- x-axis is the superset of all supplied file-backed x-axis data.
- x-axis data must be strictly increasing (no repeats, no decreases).
- x-axis need not have homogeneous timesteps in source files.
- Global x-axis timestep is the smallest positive `delta x` across file-backed sources.
- All sources are aligned to a common x-grid by linear interpolation.
- No extrapolation outside a source's x-range.
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
- Supported functions (current minimum set): `average()`, `rms()`, `abs()`, `ddt()`
- `ddt()` rule:
  - derivative is computed by finite difference on aligned x-grid
  - first timestep value equals the second timestep value (when available)
- Unit rules (current implementation):
  - `+/-`: units must match
  - `*`: composed unit string (for example `v*v`)
  - `/`: composed unit string (for example `v/s`)
  - `average/rms/abs`: preserves input unit
  - `ddt(x)`: unit becomes `<unit>/s`
- Expressions are currently intended to be used with at least one file-backed input.

## Plotting Rules

- When two y-axis types are present, use `uPlot` dual y-axis support.
- Y-axis labels: `"LongUnit (SI_prefix + ShortUnit)"` — e.g., `"Voltage (mv)"`, `"Current (mi)"`.
- Summary table column headers include `(SI_prefix + ShortUnit)` when all traces share a single y-unit — e.g., `"Average (mv)"`.
  - When multiple y-units are present, headers omit the unit and values include inline units instead.
- Legend naming precedence (highest to lowest):
  1. CLI name (`<name>:`)
  1. Parser plugin-provided `SeriesData.name`
  1. Basename of the input file without extension
  1. Expression text with spaces removed
- The chart title is not rendered on the uPlot chart (no `title` in JS opts).
- An "Input File" table shows the source file path for each trace. Expression traces show their expression source (e.g., `expr[ddt(f1)]`) instead.
- SI display scaling must be auto-selected for readability.
  - Current heuristic target:
    - prefer max magnitude in a readable range
    - bias toward values near `1`
    - examples: `1e-6 s -> us`, `~1 v -> v`
