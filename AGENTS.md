# AGENTS.md

Compressed agent onboarding for `time-plot`. Full specs: `doc/architecture.md`, `doc/plugins.md`.

## What This Is

CLI tool that plots time-series data → self-contained HTML (embedded uPlot JS/CSS). Pluggable parsers, expression-derived traces, dual y-axis, SI auto-scaling. Python ≥3.14, managed with `uv`.

## Setup & Commands

```
uv sync --group dev                        # install deps
uv run time_plot <sources...>              # run CLI
uv run python main.py <sources...>         # dev fallback
uv run pytest -q                           # tests
uv run ruff check .                        # lint
uv run ty check                            # type check
uv run python scripts/generate_example_data.py  # regen example data
```

**Validate after changes:** `uv run pytest -q` then `uv run time_plot --no-open-browser time_plot/example_data/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'`

## File Layout

```
main.py                          # dev entrypoint → cli.main()
time_plot/
  cli.py                         # rich-click CLI, parses source specs
  processing.py                  # load → align x-grid → eval expressions
  plotting.py                    # HTML gen, embeds uPlot, dual y-axis, summary tables
  models.py                      # SeriesData dataclass
  plugin_system.py               # discover/load plugins from plugins/
  units.py                       # SI prefix selection, unit parsing
  example_data.py                # example data generation logic
  example_data/                  # bundled sine.csv, cosine.csv, spice_pwl.spi, .totalcurrent
  plugins/
    voltage_or_current_vs_time/  # 2-col CSV: time(unit),voltage|current(unit)
    spice_pwl/                   # SPICE netlist PWL sources
    cadence_dynamic_power_totalcurrent/  # .totalcurrent 3-col tab-separated
tests/                           # pytest: per-module + CLI integration
doc/                             # architecture.md, plugins.md, example_data.md
scripts/generate_example_data.py # regenerates example_data/
pyproject.toml                   # deps: click, numpy, rich-click, uplot-python
```

## Data Pipeline

```
CLI args → plugin_system: discover & select plugin
  → processing: load files → align to common x-grid → eval expressions
  → plotting: generate self-contained HTML with embedded uPlot
```

## Key Data Models (processing.py, models.py)

- **SeriesData**: `source_name, name, x_label, y_label, x_unit, y_unit, y_unit_label, x, y` (float64 numpy). Plugins return `list[SeriesData]`.
- **InputFileSpec**: `arg_position, path, data_source_name, cli_name`
- **LoadedDataset**: `dataset_name, legend_name, source_path, plugin_name, series`
- **AlignedTrace**: `dataset_name, legend_name, source_name, source_path, y_label, y_unit, y_unit_label, y`
- **AlignedPlotData**: `x_seconds, traces: list[AlignedTrace], x_timestep_seconds`
- **ExpressionSpec**: `arg_position, dataset_name, legend_name, expression_text`

## Naming Rules (Flat Namespace)

- **data_source_name**: CLI `name:path` or file stem; `expr` is reserved; auto-bumps on collision (`foo_1`).
- **data_set_name**: single-series → `data_source_name`; multi-series → `SeriesData.name`; cross-source collisions → `source__name` prefix.
- **Expression names**: `name:expr[...]` or auto `e1, e2, ...`; must not collide with file-backed names.
- **Legend**: CLI name > `SeriesData.name` > file stem. Expressions: `name:compact_expr` or just `compact_expr`.

## Processing Rules

- x-axis always seconds internally; must be strictly increasing.
- Global x-grid: union of all source x-values; timestep = smallest positive Δx; exact x_max included.
- Alignment by linear interpolation; no extrapolation (NaN outside range).
- Max 2 distinct y_unit values per plot (dual y-axis).

## Expression System (safe AST walker)

- Operators: `+`, `-`, `*`, `/`
- Functions: `average()`, `rms()`, `abs()`, `ddt()`
- `+/-` require matching units; `*`/`/` produce composed strings (`v*v`, `v/s`); `ddt(x)` → `unit/s`
- Chained expressions supported; circular refs detected as errors.
- `ddt()`: finite difference, first sample = second sample value.

## Plugin API

Plugins in `time_plot/plugins/<name>/`, auto-discovered (sorted). Must export:
- `identify(path: Path) -> bool`
- `parse(path: Path, options: dict[str, str]) -> list[SeriesData]`
- Optional `plugin_name() -> str`

SeriesData must provide: `name`, `y_unit` (no SI prefix, e.g. `"v"`), `y_unit_label`, x in seconds, float64 arrays.

**Current plugins:** `voltage_or_current_vs_time` (.csv), `spice_pwl` (.spi), `cadence_dynamic_power_totalcurrent` (.totalcurrent)

## Plotting

- Self-contained HTML: uPlot JS/CSS inlined from `uplot-python` package.
- Mousewheel zoom, drag-to-zoom, dual y-axis, summary stats table (Peak |y|, Average, RMS), source table.
- SI display auto-scaling per axis. 10-color Tableau palette.

## Coding Standards

- Use `pathlib`. Prefer clear names. Update docs when behavior changes.
- **Keep `README.md` in sync.** Any change to CLI options, features, plugins, expressions, naming rules, or output behavior must be reflected in `README.md`. Treat a stale README as a bug.
- Add/update tests for behavior changes. Use `uv` for all commands.
- `local_build_backend.py` = custom PEP 517 backend; don't touch unless changing build system.
- Check for local changes before editing shared files.

## Handoff

Summarize changes, note follow-ups/risks, list validation commands run and outcomes.
