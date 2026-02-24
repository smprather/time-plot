**Conversation Summary (Restart Context)**

Project: `time-plot` (`/home/myles/time-plot`)

Goal:

- Build a plugin-based time-series plotting CLI that parses CSV files, supports expressions, aligns datasets on a common x-grid, and outputs self-contained offline HTML plots using Dygraphs.

**What Was Implemented**

1. Plugin system

- Deterministic plugin discovery from `plugins/` (sorted order).
- Seed plugin renamed/implemented as `voltage-vs-time-csv` in `plugins/voltage_vs_time_csv`.
- Recognizes `.csv` files with headers like `time(ns),voltage(v)` and ignores units in header matching.
- Parses units from parentheticals and converts to base SI (`s`, `v`).

2. Units and scaling

- Added `time_plot/units.py`.
- Input units are parsed and normalized to base SI.
- Plotting auto-selects readable SI prefixes for display (ASCII prefixes like `u`).

3. Sample/example data

- Added generation for `sample_data/sine.csv` and `sample_data/cosine.csv`.
- Headers use unit parentheticals (for example `time(ns),voltage(mv)`).
- Added CLI command `sample-files`.
- Added script `scripts/generate_example_data.py`.

4. CLI

- Click-based CLI implemented.
- Supports:
  - files
  - named files (`name:path`)
  - expressions (`expr[...]` and `name:expr[...]`)
  - default names `fN`
- `main.py` entrypoint remains a dev fallback.

5. Multi-file processing

- Added x-axis alignment/interpolation onto a common deterministic grid.
- Validates strictly increasing x.
- Uses smallest timestep across inputs as global timestep.
- Includes exact `x_max` endpoint even if off-grid.
- No extrapolation outside source ranges (`NaN`).

6. Expressions

- Safe AST-based evaluator in processing path.
- Supported operators: `+`, `-`, `*`, `/`
- Supported functions: `sin()`, `cos()`, `ddt()`
- Supports chained expressions and references to named inputs/expressions.
- Detects circular references, unknown references, duplicate dataset names.
- `ddt()` sets first output sample equal to second sample when available.

7. Plotting / HTML output

- Dygraphs HTML output supports multi-trace plotting.
- Dual y-axis support (up to 2 y-axis types).
- HTML is self-contained and offline:
  - Dygraphs JS/CSS vendored and embedded inline
  - no CDN dependency
- SVG fallback renderer remains in place if Dygraphs is unavailable.

8. Build/sync tooling

- Added local PEP 517 backend (`local_build_backend.py`) to support offline `uv build`.
- Implemented editable install hooks so `uv sync` and `uv run pytest` work properly with live workspace code.

**Tests Added**

- `tests/test_units.py`
- `tests/test_voltage_time_csv_plugin.py`
- `tests/test_sample_data.py`
- `tests/test_cli_parsing.py`
- `tests/test_processing.py`
- `tests/test_plotting.py`
- `tests/test_cli_integration.py`

Recent validations passed, including:

- `uv sync --group dev --reinstall-package time-plot`
- `uv run pytest ...` (integration/processing/plotting suites all passing)

**Commits Made**

- `092fb54` Initial plugin-based time plot prototype
- `6a1b0ce` Add seed plugin utility data workflow and CLI parsing groundwork
- `4487b40` Add multi-file alignment and combined plotting
- `afc1960` Add expression evaluation for aligned datasets
- `097b12b` Harden alignment grid and expression naming checks
- `1c2e01c` Store global timestep and fix editable installs

**AGENTS.md Work**

- User iteratively updated `AGENTS.md`.
- I reviewed and implemented corresponding code changes multiple times.
- Latest pass was a cleanup/rewrite of `AGENTS.md` only (no code changes), adding:
  - `Current Implemented Features`
  - `Known Limitations (Current)`
  - `MVP Scope (Next Work)`
  - `Project Goals (Target Behavior)`
  - clearer naming/terminology
  - expression semantics clarifications
  - plotting/data-model clarifications
  - validation checklist

**Current Repo State**

- Codebase is in a working state with committed implementation through expression/alignment/plotting features.
- `AGENTS.md` had uncommitted changes after the last session (cleanup/rewrite was applied but not committed).

**Likely Next Steps**

1. Extend expression function set beyond `sin`, `cos`, `ddt`.
1. Improve unit semantics for expression outputs (stricter composed-unit handling).
1. Add more plugins / second y-axis data type examples to exercise dual-axis behavior end-to-end.
1. Refine legend precedence and UX edge cases if needed.

If you want, I can also format this as a shorter “new-session bootstrap prompt” version.
