# time-plot

Plot arbitrary time-series data (non-calendar x-axis) into self-contained HTML using `uPlot`, with a pluggable parser system and expression-based derived traces.

## What It Does

- Loads one or more input files via auto-discovered parser plugins.
- Converts all data to base units and aligns traces to a common time grid.
- Evaluates derived traces from expressions (`expr[...]`), including chained expressions.
- Renders interactive offline HTML plots with summary statistics and input/source metadata.
- Supports dual y-axes (up to two distinct y-units per plot).

## Requirements

- Python `>=3.14`
- [`uv`](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync --group dev
```

Run via installed CLI entry point:

```bash
uv run time_plot --help
```

Dev fallback entry point:

```bash
uv run python main.py --help
```

## Quick Start

Generate sample inputs:

```bash
uv run python scripts/generate_example_data.py
```

Render a single input file:

```bash
uv run time_plot example_data/sine.csv
```

Render file + derived expressions:

```bash
uv run time_plot example_data/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'
```

If you run `time_plot` with no positional sources, it defaults to `example_data/sine.csv`.

## CLI Usage

```text
time_plot [OPTIONS] [SOURCES]...
```

Options:

- `-o, --output FILE`: output HTML path.
- `--plugins-dir DIRECTORY`: plugin directory override (default: `plugins/` in repo root).
- `--parser-options TEXT`: comma-separated `key=value` pairs passed to plugins.

Positional `SOURCES` can be:

- File path: `example_data/sine.csv`
- Named file: `sine_a:example_data/sine.csv`
- Expression: `expr[sine+sine]`
- Named expression: `sum:expr[sine+sine]`

Quote expressions in the shell.

## Output Behavior

- Default output path for a single input source: `plots/<input-stem>.html`
- Default output path for multiple sources: `plots/combined.html`
- Plot HTML is self-contained (inlines `uPlot` JS/CSS assets).
- Output includes an interactive chart with mousewheel zoom support.
- Output includes a summary table (`Peak |y|`, `Average`, `RMS`).
- Output includes a source table (`Label`, `Input File` or expression source).

## Supported Input Formats (Built-in Plugins)

### 1) Voltage/Current vs. Time CSV

- Plugin ID: `voltage-or-current-vs-time`
- File type: `.csv`
- Expected header shape (2 columns): `time(<unit>),voltage(<unit>)` or `time(<unit>),current(<unit>)`
- Example:

```csv
time(ns),voltage(mv)
0,0
1,0.5
```

### 2) SPICE PWL

- Plugin ID: `spice-pwl`
- Parses SPICE netlists containing `pwl` voltage or current sources.
- Supports line continuations with leading `+`.
- Rejects files mixing voltage and current source types.
- One PWL source becomes one plotted dataset.
- Supports parser option `naming_method` with values `element_name` (default) or `positive_node_name`.

Example:

```bash
uv run time_plot example_data/spice_pwl.spi --parser-options naming_method=positive_node_name
```

## Expressions

Expression syntax:

- `expr[<expression>]` or `<name>:expr[<expression>]`
- References use dataset names in a flat namespace.

Supported operators:

- `+`, `-`, `*`, `/`

Supported functions:

- `average(x)`
- `rms(x)`
- `abs(x)`
- `ddt(x)` (finite-difference derivative over aligned time grid)

Examples:

```bash
uv run time_plot example_data/sine.csv 'expr[sine+sine]'
uv run time_plot example_data/sine.csv 'sum:expr[sine+sine]' 'rate:expr[ddt(sum)]'
```

Expression rules:

- Unnamed expressions auto-name as `e1`, `e2`, ...
- Expression names must be valid Python identifiers.
- Duplicate names are errors.
- Expressions must reference known dataset names.
- Circular expression references are rejected.
- At least one file-backed dataset is required to evaluate expressions.

## Naming Rules

- File-backed dataset names default to file stem (unless explicitly named with `<name>:<path>`).
- Auto-generated file source name collisions are bumped (`foo`, `foo_1`, `foo_2`, ...).
- Multi-series plugin name collisions are prefixed as `<data_source_name>__<raw_name>`.
- `expr` is a reserved source name and cannot be used as a CLI name.

## Units and Axes

- Internal x-axis storage is always seconds.
- Plugins normalize values to base units (for example `mv` -> `v`, `ns` -> `s`).
- Display scaling uses automatic SI prefixes for readability.
- `+` and `-` require matching units.
- `*` and `/` produce composed unit strings.
- A single plot supports at most two distinct y-units.

## Plugin System

Plugins are discovered from a directory (`plugins/` by default) in deterministic sorted order. The first plugin whose `identify(path)` returns `True` handles the file.

A plugin must provide:

- `identify(path: Path) -> bool`
- `parse(path: Path, options: dict[str, str]) -> list[SeriesData]`
- Optional `plugin_name() -> str`

See [`doc/plugins.md`](doc/plugins.md) for current plugin details.

## Development

Run tests:

```bash
uv run pytest -q
```

Run linters/type checks:

```bash
uv run ruff check .
uv run ty check
```

Generate example data:

```bash
uv run python scripts/generate_example_data.py
```

Useful validation commands:

```bash
uv run pytest -q
uv run python scripts/generate_example_data.py
uv run time_plot example_data/sine.csv
uv run time_plot example_data/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'
```

## Repository Layout

- `time_plot/`: CLI, processing, plotting, units, plugin loading.
- `plugins/`: parser plugins.
- `example_data/`: generated sample files.
- `scripts/`: project utilities.
- `tests/`: automated tests.
- `doc/`: architecture and plugin docs.

## Troubleshooting

- `Input file not found ...`: generate sample inputs with `uv run python scripts/generate_example_data.py` or pass a valid path.
- `No plugins found ...`: verify `plugins/` exists or pass `--plugins-dir`.
- `No plugin recognized file ...`: check file format/header and plugin coverage.
- `Unknown dataset referenced in expression ...`: use correct dataset names.
- `At most two distinct y-axis units are supported.`: split traces into separate plots if needed.

## Documentation

- Architecture: [`doc/architecture.md`](doc/architecture.md)
- Plugins: [`doc/plugins.md`](doc/plugins.md)
- Example data: [`doc/example_data.md`](doc/example_data.md)

## License

MIT. See [`LICENSE`](LICENSE).
