# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

Requires `uv` and Python 3.14+.

```bash
uv sync --group dev
```

## Common Commands

```bash
uv run time_plot -f <files...>             # Run CLI (installed entry point)
uv run python main.py -f <files...>        # Dev fallback entry point
uv run pytest -q                           # Run all tests
uv run pytest -q tests/test_processing.py  # Run a single test file
uv run ruff check .                        # Lint
uv run ty check                            # Type check
uv run python scripts/generate_example_data.py  # Regenerate example data
```

## Validation Checklist

After changes, verify:

1. `uv run pytest -q`
2. `uv run python scripts/generate_example_data.py`
3. `uv run time_plot --no-open-browser -f time_plot/example_data/sine.csv`
4. `uv run time_plot --no-open-browser -f time_plot/example_data/sine.csv -e "sum=sine+sine" -e "r=ddt(sum)"`

## Architecture

### Data Pipeline

```
CLI -f/-F/-R/-e flags (cli.py)
  → plugin_system.py: discover & load plugins from multiple dirs
  → processing.py: build FileGroups → load via registry → apply filters → align to common x-grid → evaluate expressions
  → plotting.py: generate self-contained HTML with embedded uPlot JS/CSS
```

### Key Modules

- **`time_plot/cli.py`** — CLI entry point (rich-click). Order-sensitive `-f/-F/-R/-e` flags. Positional args are errors.
- **`time_plot/processing.py`** — Core pipeline: FileGroup-based loading, series registry (keyed by `realpath|series_name`), glob/regex filtering, x-grid alignment, expression evaluation, RMS sorting.
- **`time_plot/expr_parser.py`** — Custom recursive descent expression parser. Series refs use `file|series` pattern syntax with glob matching. Returns series, scalars, or array-of-series.
- **`time_plot/plotting.py`** — HTML generation. Embeds uPlot JS/CSS from `uplot-python` package. Handles dual y-axis, SI unit auto-scaling, closest-series highlighting.
- **`time_plot/models.py`** — Data models: `SeriesData`.
- **`time_plot/plugin_system.py`** — Discovers and loads parser plugins from multiple directories with precedence ordering.
- **`time_plot/units.py`** — SI prefix selection and unit display.

### Parser Plugins

Plugins live in `time_plot/plugins/<name>/` and are auto-discovered. External plugin dirs also supported (see `plugin_system.discover_plugins_from_dirs`). Each plugin must implement:
- `identify(path: Path) -> bool`
- `parse(path: Path, options: dict[str, str], selected: list[str] | None) -> list[SeriesData]`

Optional:
- `list_series(path, options) -> list[str]` — cheap pre-load enumeration
- `short_description() -> str` / `long_description() -> str` — for `--list-plugins`/`--plugin-help`

Each `SeriesData` must provide: `name`, `y_unit` (no SI prefix, e.g. `"v"`), `y_unit_label`, x in seconds as `float64` numpy arrays.

Current plugins: `voltage_or_current_vs_time` (2-column CSV), `spice_pwl` (SPICE netlist PWL sources).

### Expression System

Custom recursive descent parser in `expr_parser.py`. Syntax: `-e "name=expr"`.

- Operators: `+`, `-`, `*`, `/`
- Functions: `sum(*|pat)`, `average()`, `rms()`, `abs()`, `ddt()`
- Series refs: `foo` (substring match), `file|foo` (file+series), `*|foo*` (glob)
- Return types: series (ndarray), scalar (float → horizontal line), array-of-series (list → `name|1`, `name|2`, ...)
- Unit rules: `+/-` require matching units; `*`/`/` produce composed strings; `ddt(x)` → `<unit>/s`

### Data Processing Rules

- x-axis is always time in seconds internally.
- Global x-grid: superset of all source x-values; timestep = smallest positive Δx across all sources; exact `x_max` always included.
- No extrapolation — values outside a source's range are `NaN`.
- At most **two distinct `y_unit` values** allowed per plot (dual y-axis).
- All traces sorted by RMS descending.
