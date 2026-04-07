# time-plot

Plot arbitrary time-series data (non-calendar x-axis) into self-contained HTML using `uPlot`, with a pluggable parser system and expression-based derived traces.

## What It Does

- Loads one or more input files via auto-discovered parser plugins.
- Filters series by glob (`-F`) or regex (`-R`) patterns.
- Converts all data to base units and aligns traces to a common time grid.
- Evaluates derived traces from expressions (`-e "name=expr"`), including chained expressions.
- Renders interactive offline HTML plots with summary statistics and input/source metadata.
- Supports dual y-axes (up to two distinct y-units per plot).
- Sorts all traces by RMS (descending) for readability.
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
time_plot -f path/to/data.csv
```

Render file with derived expressions:

```bash
time_plot -f sine.csv -e "sum=sine+sine" -e "rate=ddt(sum)"
```

Running with no `-f` flags opens the built-in `sine.csv` example.

## CLI Usage

```text
time_plot [OPTIONS] -f <files...> [-F <glob>] [-R <regex>] [-e <name=expr>] ...
```

### Source and Filter Flags (order-sensitive)

- `-f <path...>`: Load one or more source files. Repeatable. Shell globs work (e.g., `-f *.csv`).
- `-F <glob>`: Glob filter on series names; binds to the preceding `-f` group. No glob chars → substring match (`foo` → `*foo*`).
- `-R <regex>`: Regex filter on series names; same binding semantics as `-F`. ANDed with `-F` if both given.
- `-e "name=expr"`: Define a named expression (see [Expressions](#expressions)).
- `-i, --case-insensitive`: Apply `-F`/`-R` filters case-insensitively.

### Options

- `-o, --output FILE`: Output HTML path. Defaults to `/tmp/$USER/time_plot.html`.
- `--open-browser / --no-open-browser`: Open the output in the default browser after writing (default: `--open-browser`).
- `-l, --list-series`: List available series for each file (with `-F`/`-R` applied) and exit.
- `--rms-filter THRESHOLD`: Exclude series whose RMS is below the threshold (same units as the data).
- `--show-rms-histogram`: Print an ASCII histogram of per-series RMS values and exit.
- `--add-plugins-dir DIRECTORY`: Additional plugin directory (repeatable; last given has highest precedence).
- `--list-plugins`: List all discovered plugins with short descriptions and exit.
- `--plugin-help PLUGIN`: Show detailed help for a named plugin and exit.
- `--parser-options TEXT`: Comma-separated `key=value` pairs passed to parser plugins.

### Environment Variables

- `TIME_PLOT_EXTRA_PLUGINS_PATH`: Colon-separated list of additional plugin directories.

### Examples

```bash
time_plot -f signal.csv
time_plot -f data.ptiavg -F 'rtr_0*' -l
time_plot -f data.ptiavg -F 'rtr_0*' -e "total=sum(*|rtr_0*)"
time_plot -f a.ptiavg -F 'mac*' -f b.ptiavg -F 'cts*' -e "diff=mac|inst-cts|inst"
```

**Note:** Positional arguments (without `-f`) are not accepted and will produce an error.

## Output

- Default output path: `/tmp/$USER/time_plot.html`.
- Plot HTML is self-contained (inlines `uPlot` JS/CSS assets) — works offline.
- Interactive chart with mousewheel zoom and closest-series highlighting.
- Summary statistics table (`Peak |y|`, `Average`, `RMS`).
- Source table showing input file paths or expression text per trace.
- All traces sorted by RMS (descending).

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
- Each PWL source becomes one series.
- Parser option `naming_method`: `element_name` (default, uses the SPICE element name, e.g. `vclk`) or `positive_node_name` (uses the positive terminal name, e.g. `clk`).

```bash
time_plot -f spice_pwl.spi --parser-options naming_method=positive_node_name
```

## Expressions

Syntax: `-e "name=<expression>"`

Expressions are always named — the name is a simple Python identifier.

### Series References

Series are referenced by pattern matching against loaded series names:

- `foo`: matches any series whose name contains `foo`
- `file|foo`: matches file containing `file` and series containing `foo`
- `*|foo*`: explicit glob syntax (any file, series starting with `foo`)

### Operators

`+`, `-`, `*`, `/`

Numeric constants are supported (e.g., `-e "scaled=sine*2"`).

### Functions

- `sum(*|pat)` — aggregate matching series into a single summed trace
- `average(x)` — mean → scalar horizontal line
- `rms(x)` — RMS → scalar horizontal line
- `abs(x)` — element-wise absolute value
- `ddt(x)` — finite-difference derivative (unit → unit/s)

### Return Types

Expressions can return:

- **Series** (`np.ndarray`): a time-series trace
- **Scalar** (`float`): plotted as a horizontal line (e.g., `rms(x)`, `average(x)`)
- **Array-of-series** (`list[np.ndarray]`): expanded as `name|1`, `name|2`, ...

### Examples

```bash
time_plot -f sine.csv -e "doubled=sine*2" -e "rate=ddt(doubled)"
time_plot -f data.ptiavg -F 'rtr_0*' -e "total=sum(*|rtr_0*)"
```

### Unit Rules

- `+`/`-` require matching units.
- `*`/`/` produce composed unit strings (e.g., `v*v`, `v/s`).
- `ddt(x)` → `<unit>/s`.

## Plugin System

Plugins are discovered from `time_plot/plugins/` in deterministic sorted order. The first plugin whose `identify(path)` returns `True` handles the file.

A plugin must provide:

- `identify(path: Path) -> bool`
- `parse(path: Path, options: dict[str, str], selected: list[str] | None) -> list[SeriesData]`

Optional:

- `plugin_name() -> str`
- `list_series(path: Path, options: dict[str, str]) -> list[str]` — efficient pre-load series enumeration
- `short_description() -> str` — one-line summary for `--list-plugins`
- `long_description() -> str` — detailed help for `--plugin-help`

Plugin search order (highest precedence first):

1. `--add-plugins-dir` flags (last given = first checked)
2. `TIME_PLOT_EXTRA_PLUGINS_PATH` entries
3. Built-in `time_plot/plugins/` directory

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
uv run time_plot --no-open-browser -f time_plot/example_data/sine.csv
uv run time_plot --no-open-browser -f time_plot/example_data/sine.csv -e "sum=sine+sine" -e "r=ddt(sum)"
```

## Repository Layout

- `time_plot/`: CLI, processing, plotting, units, plugin system, expression parser.
- `time_plot/plugins/`: parser plugins.
- `time_plot/example_data/`: bundled sample files.
- `time_plot/vendor/`: vendored third-party code (ascii-histogram).
- `scripts/`: developer utilities.
- `tests/`: automated tests.
- `doc/`: architecture and plugin docs.

## Troubleshooting

- `Input file not found`: check the path; generate sample files with `uv run python scripts/generate_example_data.py`.
- `No plugin recognized file`: check file format and suffix against supported plugins.
- `Series reference matched no loaded series`: verify the series name pattern matches loaded data. Use `-l` to list available series.
- `At most two distinct y-axis units are supported`: split traces into separate `time_plot` invocations.
- `Unexpected argument`: positional arguments are not supported. Use `-f` to specify source files.

## License

MIT. See [`LICENSE`](LICENSE).
