# time-plot

Plot arbitrary time-series data (non-calendar x-axis) into self-contained HTML using `uPlot`, with a pluggable parser system and expression-based derived traces.

## What It Does

- Loads one or more input files via auto-discovered parser plugins.
- Converts all data to base units and aligns traces to a common time grid.
- Evaluates derived traces from expressions (`expr[...]`), including chained expressions.
- Renders interactive offline HTML plots with summary statistics and input/source metadata.
- Supports dual y-axes (up to two distinct y-units per plot).
- Opens the result in your browser automatically.

## Requirements

- Python `>=3.14`
- [`uv`](https://docs.astral.sh/uv/)

## Installation

Install as a user tool (recommended):

```bash
uv tool install git+https://github.com/smprather/time-plot
```

Then run anywhere:

```bash
time_plot --help
```

## Quick Start

Render a single input file:

```bash
time_plot path/to/data.csv
```

Render file + derived expressions:

```bash
time_plot path/to/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'
```

Running with no positional sources opens the built-in `sine.csv` example.

## CLI Usage

```text
time_plot [OPTIONS] [SOURCES]...
```

Options:

- `-o, --output FILE`: output HTML path. Defaults to `./plots/<input-stem>.html`.
- `--open-browser / --no-open-browser`: open the output in the default browser after writing (default: `--open-browser`).
- `--plugins-dir DIRECTORY`: plugin directory override.
- `--parser-options TEXT`: comma-separated `key=value` pairs passed to plugins.

Positional `SOURCES` can be:

- File path: `data.csv`
- Named file: `my_name:data.csv`
- Expression: `expr[sine+sine]`
- Named expression: `sum:expr[sine+sine]`

Quote expressions in the shell to avoid interpretation of `[` and `]`.

## Output

- Default output path for a single input source: `./plots/<input-stem>.html`
- Default output path for multiple sources: `./plots/combined.html`
- Plot HTML is self-contained (inlines `uPlot` JS/CSS assets) — works offline.
- Interactive chart with mousewheel zoom.
- Summary statistics table (`Peak |y|`, `Average`, `RMS`).
- Source table showing input file paths or expression text per trace.

## Supported Input Formats

### 1) Voltage/Current vs. Time CSV

- Plugin ID: `voltage-or-current-vs-time`
- File type: `.csv`
- Two-column header: `time(<unit>),voltage(<unit>)` or `time(<unit>),current(<unit>)`

```csv
time(ns),voltage(mv)
0,0
1,0.5
```

### 2) SPICE PWL

- Plugin ID: `spice-pwl`
- Parses SPICE netlists containing `pwl` voltage or current sources.
- Supports line continuations with leading `+`.
- Each PWL source becomes one dataset.
- Parser option `naming_method`: `element_name` (default) or `positive_node_name`.

```bash
time_plot spice_pwl.spi --parser-options naming_method=positive_node_name
```

### 3) Cadence Dynamic Power Total Current

- Plugin ID: `cadence-dynamic-power-totalcurrent`
- File type: `.totalcurrent`
- Three tab-separated columns: row index, time (seconds, scientific notation), current (amps).

```bash
time_plot VDD.peak.totalcurrent
```

## Expressions

Syntax: `expr[<expression>]` or `<name>:expr[<expression>]`

References use dataset names (flat namespace, valid Python identifiers).

Operators: `+`, `-`, `*`, `/`

Functions:

- `average(x)` — mean over the time grid
- `rms(x)` — RMS over the time grid
- `abs(x)` — element-wise absolute value
- `ddt(x)` — finite-difference derivative

```bash
time_plot sine.csv 'sum:expr[sine+sine]' 'rate:expr[ddt(sum)]'
```

Rules:

- Unnamed expressions auto-name as `e1`, `e2`, ...
- Circular references and unknown names are errors.
- `+`/`-` require matching units; `*`/`/` produce composed unit strings.

## Naming

- File-backed dataset names default to file stem (`sine.csv` → `sine`).
- Explicit name: `my_name:/path/to/file.csv`
- Auto-generated name collisions are bumped: `foo`, `foo_1`, `foo_2`, ...
- Multi-series name collisions are prefixed: `<source>__<series>`
- `expr` is a reserved name.

## Plugin System

Plugins are discovered from `time_plot/plugins/` in deterministic sorted order. The first plugin whose `identify(path)` returns `True` handles the file.

A plugin must provide:

- `identify(path: Path) -> bool`
- `parse(path: Path, options: dict[str, str]) -> list[SeriesData]`
- Optional `plugin_name() -> str`

Override the search directory with `--plugins-dir`.

## Development

```bash
git clone https://github.com/smprather/time-plot
cd time-plot
uv sync --group dev
```

Run tests:

```bash
uv run pytest -q
```

Lint and type check:

```bash
uv run ruff check .
uv run ty check
```

Regenerate example data:

```bash
uv run python scripts/generate_example_data.py
```

Validation:

```bash
uv run pytest -q
uv run time_plot --no-open-browser time_plot/example_data/sine.csv
uv run time_plot --no-open-browser time_plot/example_data/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'
```

## Repository Layout

- `time_plot/`: CLI, processing, plotting, units, plugin system.
- `time_plot/plugins/`: parser plugins.
- `time_plot/example_data/`: bundled sample files.
- `scripts/`: developer utilities.
- `tests/`: automated tests.
- `doc/`: architecture and plugin docs.

## Troubleshooting

- `Input file not found`: check the path; generate sample files with `uv run python scripts/generate_example_data.py`.
- `No plugin recognized file`: check file format and suffix against supported plugins.
- `Unknown dataset referenced in expression`: verify the dataset name matches the file stem or explicit name.
- `At most two distinct y-axis units are supported`: split traces into separate `time_plot` invocations.

## License

MIT. See [`LICENSE`](LICENSE).
