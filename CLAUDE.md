# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

Requires `uv` and Python 3.14+.

```bash
uv sync --group dev
```

## Common Commands

```bash
uv run time_plot <sources...>              # Run CLI (installed entry point)
uv run python main.py <sources...>         # Dev fallback entry point
uv run pytest -q                           # Run all tests
uv run pytest -q tests/test_processing.py # Run a single test file
uv run ruff check .                        # Lint
uv run ty check                            # Type check
uv run python scripts/generate_example_data.py  # Regenerate example data
```

## Validation Checklist

After changes, verify:

1. `uv run pytest -q`
2. `uv run python scripts/generate_example_data.py`
3. `uv run time_plot example_data/sine.csv`
4. `uv run time_plot example_data/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'`

## Architecture

### Data Pipeline

```
CLI args (cli.py)
  → plugin_system.py: discover & load plugins from plugins/
  → processing.py: load files via plugins → align to common x-grid → evaluate expressions
  → plotting.py: generate self-contained HTML with embedded uPlot JS/CSS
```

### Key Modules

- **`time_plot/cli.py`** — CLI entry point (rich-click). Parses source specs (`name:path`, `name:expr[...]`).
- **`time_plot/processing.py`** — Core pipeline: file loading, x-grid alignment (linear interpolation, NaN outside range), expression evaluation (safe AST walker).
- **`time_plot/plotting.py`** — HTML generation. Embeds uPlot JS/CSS from `uplot-python` package. Handles dual y-axis and SI unit auto-scaling.
- **`time_plot/models.py`** — Data models: `SeriesData`, `LoadedDataset`, `AlignedTrace`, `AlignedPlotData`, `ExpressionSpec`.
- **`time_plot/plugin_system.py`** — Discovers and loads parser plugins from `plugins/` directory (sorted deterministically by package name).
- **`time_plot/units.py`** — SI prefix selection and unit display.

### Parser Plugins

Plugins live in `plugins/<name>/` and are auto-discovered. Each plugin must implement:
- An identification function to check if it supports a given file
- `parse(file_path, options: dict[str, str]) -> list[SeriesData]`

Each `SeriesData` must provide: `name`, `y_unit` (no SI prefix, e.g. `"v"`), `y_unit_label`, x in seconds as `float64` numpy arrays.

Current plugins: `voltage_or_current_vs_time` (2-column CSV), `spice_pwl` (SPICE netlist PWL sources).

### Namespace and Naming Rules

All `data_set`s share a **flat namespace**. Key rules:
- CLI `name:path` sets the `data_source_name`; otherwise the file stem is used.
- Single-series sources: `data_set_name` = `data_source_name`.
- Multi-series sources: plugin-returned `SeriesData.name`; collisions across sources get `source__name` auto-prefix (double underscore).
- Expressions: named via `name:expr[...]` or auto-assigned `e1`, `e2`, ...
- `expr` is a reserved name and cannot be used as a `data_source_name`.

### Expression Evaluation

Expressions are evaluated via safe AST walking. Supported operators: `+`, `-`, `*`, `/`. Supported functions: `average()`, `rms()`, `abs()`, `ddt()`. Unit rules: `+/-` require matching units; `*`/`/` produce composed strings (e.g. `v*v`, `v/s`); `ddt(x)` → `<unit>/s`. Circular references are detected and are errors.

### Data Processing Rules

- x-axis is always time in seconds internally.
- Global x-grid: superset of all source x-values; timestep = smallest positive Δx across all sources; exact `x_max` always included.
- No extrapolation — values outside a source's range are `NaN`.
- At most **two distinct `y_unit` values** allowed per plot (dual y-axis).

### Build Backend

`local_build_backend.py` is a custom PEP 517 build backend (wheel/sdist/editable installs). Editable installs use `.pth` files. Do not modify unless changing the build system.
