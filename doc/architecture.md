# Architecture

Project specification and design documentation for `time-plot`.

## Project Overview

- Project: `time-plot`
- Script name: `time_plot`
- Purpose: plot time-series data (non-calendar time on x-axis) using embedded `uPlot` JavaScript in generated
  HTML.
- Runtime: Python (`>=3.14`) managed with `uv`

## Tech Stack

- Python >= 3.14
- `uPlot` via `uplot-python` (embedded JS assets in generated HTML)
- Click CLI, using rich-click color wrapper
- Pytest
- Astral Ruff
- Astral Ty

## Repository Structure

- `main.py`: dev entry point
- `pyproject.toml`: project metadata and dependencies
- `uv.lock`: locked dependency versions
- `time_plot/`: application package
- `plugins/`: parser plugins
- example_data/: generated example data files
- `scripts/`: developer utility scripts
- `tests/`: automated tests
- `doc/`: project documentation
- `README.md`: project documentation

## Terminology

- `uPlot`: the browser plotting library used in generated HTML. JS/CSS assets are sourced from the
  `uplot-python` pip package.
- `uplot-python`: Python package providing uPlot static assets. We use only the bundled JS/CSS, not the Python
  plotting API.
- `y-axis type`: defined by `y_unit` alone. The label is cosmetic; only the unit determines axis grouping.
- `data_source`: A file containing one or more `data_set`s.
- `data_source_name`: A unique name assigned to each input file. Determined by (highest to lowest precedence):
  1. CLI `name:/path/to/file` syntax.
  2. File basename without extension (e.g., `sine` for `sine.csv`).
- `data_set`: A single named y-series over time. Every data_set lives in one flat namespace and is referenced
  by its `data_set_name` in expressions.
- `data_set_name`: The unique identifier for a data_set. Used for expression references. See naming rules
  below.
- `data_set_label`: The display string used in legends and tables. May differ from the `data_set_name`.

## Naming Rules

All `data_set` names share a single flat namespace. Every `data_set_name` must be a valid Python identifier
so it can be referenced in expressions.

### data_source_name assignment

Each input file gets a `data_source_name`:

1. **CLI name** (highest): `name:/path/to/file` — the `name` portion is the `data_source_name`.
2. **File basename** (fallback): the file stem (basename without extension).
   - If the auto-generated `data_source_name` conflicts with an existing one, use integer name-bumps:
     `foo_1`, `foo_2`, etc. Bumps are applied at the time of conflict.
   - CLI-assigned duplicate `data_source_name`s are an error.
3. `expr` is a reserved name. It is an error for `expr` to be used as a `data_source_name` on the CLI or
   returned by a plugin.

### data_set_name assignment (file-backed)

- **Single-series source**: the `data_set_name` is the `data_source_name`.
- **Multi-series source**: each series gets the `data_set_name` returned by the plugin
  (i.e., `SeriesData.name`).
  - If two or more raw `data_set_name`s collide across all sources, those entries are auto-prefixed as
    `data_source_name__raw_name` (double underscore separator).
  - Single-series entries are never prefixed because their name is already the `data_source_name`, which is
    unique.

### data_set_name assignment (expressions)

- If a name is given on the CLI: `foo:expr[...]` → `data_set_name` is `foo`.
- If no name is given: auto-assigned as `e1`, `e2`, etc. (separate counter from file-backed sources).
- It is legal to assign a name matching the auto format (e.g., `e1:expr[...]`).
- Duplicate expression `data_set_name`s are an error.
- Expression `data_set_name`s must not collide with file-backed `data_set_name`s.

### data_set_label (legend/display name)

- **File-backed**: the label is the CLI name if given, otherwise `SeriesData.name`, otherwise the file stem.
- **Expressions**:
  - User-named (does not match `^e\d+$`): `data_set_name:expression_text_with_spaces_removed`
  - Auto-named (matches `^e\d+$`): `expression_text_with_spaces_removed`

## Project Goals (Target Behavior)

- Read x, y data from multiple input sources.
- The x-axis data is time as zero-based "instants"; it is never calendar date-based.
  - Always label the x-axis as `Time (<units>)`.
- The source of x, y data should be implemented as a plugin so users can add new formats.
- Support up to two different y-axis types in a single plot.
- Support generated `data_set`s (expressions) that are functions of other `data_set`s.

## Current Implemented Features

- Plugin-based file parsing with deterministic discovery (sorted by plugin package/file name).
- Voltage/Current vs. Time CSV parser plugin:
  - Plugin ID: `voltage-or-current-vs-time`
  - Package directory: `plugins/voltage_or_current_vs_time`
- SPICE PWL parser plugin:
  - Plugin ID: `spice-pwl`
  - Package directory: `plugins/spice_pwl`
- Example data generation:
  - Refer to example_data.md
- CLI positional source parsing:
  - files
  - named files (`name:path`)
  - expressions (`expr[...]` and `name:expr[...]`)
  - file-backed sources default to file basename (no extension) as `data_source_name`
  - expression auto-naming: `eN`
- Flat data_set namespace with `__` auto-prefix for multi-series name conflicts
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
- Internal storage does not yet implement the optimization "store only min x + global timestep" for every
  data_set.
- CLI/integration coverage is focused and not exhaustive.

## MVP Scope (Next Work)

- Extend expression function set as needed (`sqrt`, filters, etc.).
  - sqrt() should be next. Don't do any other functions until requested.
- Improve expression unit semantics/simplification.
- Add more parser plugins.
- Strengthen CLI/integration tests for error cases and mixed input scenarios.

## Next Implementation Priorities

- Expand expression function set and documentation.
- Improve unit simplification/validation for expressions.
- Add stronger end-to-end CLI tests for mixed files + expressions + error conditions.
- Consider implementing compact per-data-set x storage (`x_min + global dt`) if memory/performance becomes
  relevant.

## Parser Plugin Rules

- A parser plugin is a Python package auto-discovered and imported by the main program.
- Plugins are stored in a `plugins/` directory located beside the executable script.
- A plugin must provide an identification function that checks support for a file.
- Plugin identification is attempted in deterministic order.
  - Current rule: sorted by plugin package/file name.
- The first matching plugin is used.
- `parse()` receives `(file_path, options)` where `options` is `dict[str, str]` from the CLI
  `--parser-options` flag, and returns `list[SeriesData]`. Single-data-set plugins return a one-element list.
- If a plugin supports a file, each `SeriesData` must provide:
  - `name`: a per-data_set identifier. For single-series plugins, use the file stem. For multi-series plugins,
    a unique name per series (e.g., the element name in SPICE PWL).
  - `y_unit`: short unit code with no SI prefix (e.g., `"v"`, `"a"`) — used for axis grouping and SI scaling.
  - `y_unit_label`: long-form unit name (e.g., `"Voltage"`, `"Amps"`) — used for y-axis display labels.
  - x values converted to seconds.
  - `float64` numpy arrays for x and y in base units.
  - `y_label`: literal y-axis label for the data_set.

## CLI Rules

- Positional arguments may refer to:
    1. File paths
    2. Expressions (`expr[...]`)
- A file or expression may be named with `<name>:` prefix:
  - Example: `data1:/foo/bar.csv`
  - Example: `total:expr[sine+cosine]`
- Unnamed file sources get their file basename (without extension) as the `data_source_name`.
  - Example: `time_plot foo.csv bar.csv`
  - `foo.csv` → `data_source_name` is `foo`
  - `bar.csv` → `data_source_name` is `bar`
  - If basenames collide, auto name-bumps are applied: `foo`, `foo_1`, etc.
- Unnamed expressions are auto-named `e1`, `e2`, etc. (separate counter).
- `expr` is reserved and cannot be used as a CLI name.
- Duplicate CLI-assigned names are errors.
- Expression references use `data_set_name`s (flat namespace).
  - For predictable references, use valid Python identifiers in names.
- Shell usage:
  - Quote expression arguments to avoid shell parsing issues.
  - Example: `time_plot sine.csv 'total:expr[sine+sine]'`

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
  - include the exact global `x_max` even if it is not an integer multiple of the global timestep from
    `x_min`.
- A global x-axis timestep should be stored and used.
  - Current implementation stores `x_timestep_seconds` in the aligned plot model.
- Expressions may refer to file-backed `data_set`s and other expressions.
- Names are assigned to all `data_set`s before expression evaluation.
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
- Y-axis labels: `"LongUnit (SI_prefix + ShortUnit)"` — e.g., `"Voltage (mv)"`, `"Amps (ma)"`.
- Summary table column headers include `(SI_prefix + ShortUnit)` when all traces share a single y-unit — e.g.,
  `"Average (mv)"`.
  - When multiple y-units are present, headers omit the unit and values include inline units instead.
- The chart title is not rendered on the uPlot chart (no `title` in JS opts).
- An "Input File" table shows the source file path for each trace. Expression traces show their expression
  source (e.g., `expr[ddt(f1)]`) instead.
- SI display scaling must be auto-selected for readability.
  - Current heuristic target:
    - prefer max magnitude in a readable range
    - bias toward values near `1`
    - examples: `1e-6 s -> us`, `~1 v -> v`
