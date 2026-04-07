# AGENTS.md

Compressed agent onboarding for `time-plot`. Full specs: `doc/architecture.md`, `doc/plugins.md`.

## What This Is

CLI tool that plots time-series data → self-contained HTML (embedded uPlot JS/CSS). Pluggable parsers, expression-derived traces, dual y-axis, SI auto-scaling, series filtering, RMS tools. Python ≥3.14, managed with `uv`.

## Setup & Commands

```
uv sync --group dev                        # install deps
uv run time_plot -f <files...>             # run CLI
uv run python main.py -f <files...>        # dev fallback
uv run pytest -q                           # tests
uv run ruff check .                        # lint
uv run ty check                            # type check
uv run python scripts/generate_example_data.py  # regen example data
```

**Validate after changes:** `uv run pytest -q` then `uv run time_plot --no-open-browser -f time_plot/example_data/sine.csv -e "sum=sine+sine" -e "r=ddt(sum)"`

## File Layout

```
main.py                          # dev entrypoint → cli.main()
time_plot/
  cli.py                         # rich-click CLI, -f/-F/-R/-e flags
  processing.py                  # FileGroup load → registry → align x-grid → eval expressions
  expr_parser.py                 # custom recursive descent expression parser
  plotting.py                    # HTML gen, embeds uPlot, dual y-axis, summary tables
  models.py                      # SeriesData dataclass
  plugin_system.py               # discover/load plugins from multiple dirs
  units.py                       # SI prefix selection, unit parsing
  example_data.py                # example data generation logic
  example_data/                  # bundled sine.csv, cosine.csv, spice_pwl.spi
  plugins/
    voltage_or_current_vs_time/  # 2-col CSV: time(unit),voltage|current(unit)
    spice_pwl/                   # SPICE netlist PWL sources
  vendor/
    ascii_histogram/             # vendored histogram for --show-rms-histogram
tests/                           # pytest: per-module + CLI integration
doc/                             # architecture.md, plugins.md, example_data.md
scripts/generate_example_data.py # regenerates example_data/
pyproject.toml                   # deps: click, numpy, rich-click, uplot-python
```

## Data Pipeline

```
CLI -f/-F/-R args → plugin_system: discover plugins from multiple dirs
  → processing: build FileGroups → load via registry (realpath|series_name keys)
    → apply glob/regex filters → align to common x-grid
    → eval expressions (custom parser) → sort by RMS descending
  → plotting: generate self-contained HTML with embedded uPlot
```

## CLI Flags (order-sensitive)

- `-f <path...>`: source files (repeatable, shell globs work)
- `-F <glob>`: glob filter on series names; binds to preceding `-f`
- `-R <regex>`: regex filter; same binding as `-F`, ANDed
- `-e "name=expr"`: named expression
- `-i`: case-insensitive filters
- `-o FILE`: output path (default: `/tmp/$USER/time_plot.html`)
- `-l, --list-series`: list filtered series and exit
- `--rms-filter THRESHOLD`: exclude low-RMS series
- `--show-rms-histogram`: ASCII histogram of RMS values, then exit
- `--add-plugins-dir DIR`: extra plugin dir (repeatable, last = highest precedence)
- `--list-plugins` / `--plugin-help NAME`: plugin discovery
- `--parser-options TEXT`: `key=value` pairs passed to plugins
- Env: `TIME_PLOT_EXTRA_PLUGINS_PATH` (colon-separated plugin dirs)

**Positional args are an error.** Use `-f` for files.

## Key Data Models (processing.py, models.py)

- **SeriesData**: `source_name, name, x_label, y_label, x_unit, y_unit, y_unit_label, x, y` (float64 numpy). Plugins return `list[SeriesData]`.
- **FileGroup**: `files: list[Path], glob_filter, regex_filter`
- **ExpressionDef**: `name, expr_text`
- **AlignedTrace**: `registry_key, legend_name, source_name, source_path, y_label, y_unit, y_unit_label, y`
- **AlignedPlotData**: `x_seconds, traces: list[AlignedTrace], x_timestep_seconds`

Series registry keys: `realpath|series_name` (unique per file+series).

## Processing Rules

- x-axis always seconds internally; must be strictly increasing.
- Global x-grid: union of all source x-values; timestep = smallest positive Δx; exact x_max included.
- Alignment by linear interpolation; no extrapolation (NaN outside range).
- Max 2 distinct y_unit values per plot (dual y-axis).
- All traces sorted by RMS descending.

## Expression System (custom recursive descent parser)

- Syntax: `-e "name=expr"` (name must be a simple identifier)
- Operators: `+`, `-`, `*`, `/`
- Functions: `sum(*|pat)`, `average()`, `rms()`, `abs()`, `ddt()`
- Series refs: `foo` (substring), `file|foo` (file+series), `*|foo*` (glob)
- Return types: series (ndarray), scalar (float → horizontal line), array-of-series (list → `name|1`, `name|2`, ...)
- `+/-` require matching units; `*`/`/` produce composed strings; `ddt(x)` → `unit/s`
- `rms()` and `average()` return scalars; `sum()` aggregates matching series
- `ddt()`: finite difference, first sample = second sample value.

## Plugin API

Plugins in `time_plot/plugins/<name>/`, auto-discovered (sorted). Must export:
- `identify(path: Path) -> bool`
- `parse(path: Path, options: dict[str, str], selected: list[str] | None) -> list[SeriesData]`

Optional:
- `plugin_name() -> str`
- `list_series(path: Path, options: dict[str, str]) -> list[str]` — cheap pre-load enumeration
- `short_description() -> str` — for `--list-plugins`
- `long_description() -> str` — for `--plugin-help`

SeriesData must provide: `name`, `y_unit` (no SI prefix, e.g. `"v"`), `y_unit_label`, x in seconds, float64 arrays.

**Current plugins:** `voltage_or_current_vs_time` (.csv), `spice_pwl` (.spi/.sp/.cir/.net/.spice)

Plugin search order: `--add-plugins-dir` (last=first) → `TIME_PLOT_EXTRA_PLUGINS_PATH` → built-in `plugins/`.

## Plotting

- Self-contained HTML: uPlot JS/CSS inlined from `uplot-python` package.
- Mousewheel zoom, drag-to-zoom, closest-series highlighting (cursor.focus.prox=30).
- Dual y-axis, summary stats table (Peak |y|, Average, RMS), source table.
- SI display auto-scaling per axis. 10-color Tableau palette.

## Coding Standards

- Use `pathlib`. Prefer clear names. Update docs when behavior changes.
- **Keep `README.md` in sync.** Any change to CLI options, features, plugins, expressions, naming rules, or output behavior must be reflected in `README.md`. Treat a stale README as a bug.
- Add/update tests for behavior changes. Use `uv` for all commands.
- Check for local changes before editing shared files.

## Handoff

Summarize changes, note follow-ups/risks, list validation commands run and outcomes.
