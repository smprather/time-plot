"""Core data pipeline: load files, build series registry, align, evaluate expressions."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from time_plot.expr_parser import (
    EvalResult,
    evaluate,
    parse_expr_def,
)
from time_plot.models import SeriesData
from time_plot.plugin_system import ParserPlugin, select_plugin


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FileGroup:
    """A set of source files sharing the same filter."""
    files: list[Path]
    glob_filter: str | None = None    # from -F; None means '*' (all)
    regex_filter: str | None = None   # from -R


@dataclass(slots=True)
class ExpressionDef:
    """A named expression from -e 'name=expr'."""
    name: str
    expr_text: str


@dataclass(slots=True)
class AlignedTrace:
    """A single time-series after alignment to the global x-grid."""
    registry_key: str           # realpath|series_name
    legend_name: str            # display name
    source_name: str            # plugin source_name or 'expr[...]'
    source_path: Path | None    # None for expression results
    y_label: str
    y_unit: str
    y_unit_label: str
    y: np.ndarray
    y_display_prefix: str | None = None


@dataclass(slots=True)
class AlignedPlotData:
    x_seconds: np.ndarray
    traces: list[AlignedTrace]
    x_timestep_seconds: float | None = None
    x_display_prefix: str | None = None


# ---------------------------------------------------------------------------
# Series registry
# ---------------------------------------------------------------------------

@dataclass
class _RegistryEntry:
    series: SeriesData
    source_path: Path
    plugin_name: str


def _registry_key(path: Path, series_name: str) -> str:
    return f"{path.resolve()}|{series_name}"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def list_series_for_groups(
    groups: list[FileGroup],
    plugins: list[ParserPlugin],
    parser_options: dict[str, str] | None = None,
    case_insensitive: bool = False,
) -> dict[Path, list[str]]:
    """Return filtered series names per file without loading data.

    For plugins that implement list_series, the listing is cheap (no data load).
    For plugins that don't, parse() is called with selected=None and names are
    collected from the returned SeriesData objects.
    """
    opts = parser_options or {}
    result: dict[Path, list[str]] = {}

    for group in groups:
        for file_path in group.files:
            plugin = select_plugin(file_path, plugins)
            if plugin.list_series is not None:
                all_names = plugin.list_series(file_path, opts)
            else:
                series_list = plugin.parse(file_path, opts, None)
                all_names = [s.name for s in series_list]

            filtered = _apply_filter(all_names, group, case_insensitive=case_insensitive)
            result[file_path] = filtered

    return result


def load_file_groups(
    groups: list[FileGroup],
    plugins: list[ParserPlugin],
    parser_options: dict[str, str] | None = None,
    case_insensitive: bool = False,
) -> dict[str, _RegistryEntry]:
    """Load all files from all groups, applying filters, and return the series registry."""
    opts = parser_options or {}
    registry: dict[str, _RegistryEntry] = {}

    for group in groups:
        for file_path in group.files:
            plugin = select_plugin(file_path, plugins)
            selected = _select_series(file_path, plugin, opts, group, case_insensitive=case_insensitive)
            series_list = plugin.parse(file_path, opts, selected)
            for series in series_list:
                key = _registry_key(file_path, series.name)
                if key in registry:
                    raise ValueError(
                        f"Duplicate series key in registry: {key!r}"
                    )
                registry[key] = _RegistryEntry(
                    series=series,
                    source_path=file_path,
                    plugin_name=plugin.plugin_name,
                )

    return registry


def _select_series(
    file_path: Path,
    plugin: ParserPlugin,
    opts: dict[str, str],
    group: FileGroup,
    case_insensitive: bool = False,
) -> list[str] | None:
    """Return the list of series names to extract, or None to load all."""
    has_filter = group.glob_filter is not None or group.regex_filter is not None
    if not has_filter:
        # No filter — plugins without list_series load everything
        return None

    if plugin.list_series is None:
        # Plugin can't enumerate series; load all and filter post-parse.
        # Caller (_load_with_filter) handles post-parse filtering.
        return None

    all_names = plugin.list_series(file_path, opts)
    return _apply_filter(all_names, group, case_insensitive=case_insensitive)


def _apply_filter(names: list[str], group: FileGroup, case_insensitive: bool = False) -> list[str]:
    result = names
    if group.glob_filter is not None:
        pat = _glob_to_match_pattern(group.glob_filter)
        if case_insensitive:
            result = [n for n in result if fnmatch.fnmatch(n.lower(), pat.lower())]
        else:
            result = [n for n in result if fnmatch.fnmatch(n, pat)]
    if group.regex_filter is not None:
        flags = re.IGNORECASE if case_insensitive else 0
        rx = re.compile(group.regex_filter, flags)
        result = [n for n in result if rx.search(n)]
    return result


def _glob_to_match_pattern(pat: str) -> str:
    """If pattern has no glob chars, treat as *pat* (substring)."""
    if not any(c in pat for c in "*?[]"):
        return f"*{pat}*"
    return pat


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def align_registry(
    registry: dict[str, _RegistryEntry],
) -> AlignedPlotData:
    """Align all registry entries to a common x-grid."""
    if not registry:
        raise ValueError("No series loaded")

    entries = list(registry.items())
    series_list = [e.series for _, e in entries]

    for key, entry in entries:
        _validate_strictly_increasing_x(entry.series.x, entry.source_path)

    x_arrays = [s.x for s in series_list]
    dt = _smallest_positive_dx(x_arrays)
    x_min = min(float(arr[0]) for arr in x_arrays)
    x_max = max(float(arr[-1]) for arr in x_arrays)
    x_grid = _uniform_grid(x_min, x_max, dt)

    traces: list[AlignedTrace] = []
    for key, entry in entries:
        s = entry.series
        y_grid = _interpolate_onto_grid(s.x, s.y, x_grid)
        traces.append(AlignedTrace(
            registry_key=key,
            legend_name=s.name,
            source_name=s.source_name,
            source_path=entry.source_path,
            y_label=s.y_label,
            y_unit=s.y_unit,
            y_unit_label=s.y_unit_label,
            y=y_grid,
            y_display_prefix=s.y_display_prefix,
        ))

    y_units = {t.y_unit for t in traces}
    if len(y_units) > 2:
        raise ValueError("At most two distinct y-axis units are supported.")

    return AlignedPlotData(
        x_seconds=x_grid,
        traces=traces,
        x_timestep_seconds=dt,
        x_display_prefix=series_list[0].x_display_prefix if series_list else None,
    )


# ---------------------------------------------------------------------------
# Expression evaluation
# ---------------------------------------------------------------------------

def evaluate_expressions(
    aligned: AlignedPlotData,
    expr_defs: list[ExpressionDef],
    registry: dict[str, _RegistryEntry],
) -> list[AlignedTrace]:
    """Evaluate named expressions and return new AlignedTraces."""
    if not expr_defs:
        return []

    x = aligned.x_seconds

    # Build lookup maps from registry keys
    trace_by_key: dict[str, AlignedTrace] = {t.registry_key: t for t in aligned.traces}

    # Expression namespace: name → EvalResult (checked before registry)
    expr_ns: dict[str, EvalResult] = {}

    produced: list[AlignedTrace] = []

    for expr_def in expr_defs:
        name = expr_def.name
        if name in expr_ns:
            raise ValueError(f"Duplicate expression name: {name!r}")

        _, ast = parse_expr_def(f"{name}={expr_def.expr_text}")

        def make_resolve(
            trace_by_key: dict[str, AlignedTrace] = trace_by_key,
            expr_ns: dict[str, EvalResult] = expr_ns,
            registry: dict[str, _RegistryEntry] = registry,
        ):
            def resolve(a_pat: str | None, b_pat: str, context: str) -> ExprResult:
                # 1. Check expression namespace first (exact name match on b_pat)
                if a_pat is None and b_pat in expr_ns and not any(c in b_pat for c in "*?[]"):
                    return expr_ns[b_pat]

                # 2. Pattern-match against registry keys
                a_match = _glob_to_match_pattern(a_pat) if a_pat is not None else "*"
                b_match = _glob_to_match_pattern(b_pat)

                matches: list[tuple[str, AlignedTrace]] = []
                for key, trace in trace_by_key.items():
                    realpath_str, series_name = key.rsplit("|", 1)
                    file_base = Path(realpath_str).name
                    if fnmatch.fnmatch(file_base, a_match) and fnmatch.fnmatch(series_name, b_match):
                        matches.append((key, trace))

                if context == "scalar":
                    if len(matches) == 0:
                        raise ValueError(
                            f"Series reference {_fmt_ref(a_pat, b_pat)!r} matched no loaded series"
                        )
                    if len(matches) > 1:
                        names = ", ".join(k for k, _ in matches)
                        raise ValueError(
                            f"Series reference {_fmt_ref(a_pat, b_pat)!r} is ambiguous — "
                            f"matched {len(matches)} series: {names}"
                        )
                    t = matches[0][1]
                    return EvalResult(value=t.y, y_unit=t.y_unit, y_unit_label=t.y_unit_label, y_label=t.y_label)

                # array context
                if not matches:
                    # Return an EvalResult with empty list — unit unknown
                    return EvalResult(value=[], y_unit="?", y_unit_label="", y_label=b_pat)
                # Infer unit from first match
                first = matches[0][1]
                return EvalResult(
                    value=[t.y for _, t in matches],
                    y_unit=first.y_unit,
                    y_unit_label=first.y_unit_label,
                    y_label=b_pat,
                )

            return resolve

        result = evaluate(ast, make_resolve(), x)

        # Expand scalar (float) to horizontal line
        val = result.value
        if isinstance(val, float):
            if not np.isfinite(val):
                arr = np.full_like(x, np.nan, dtype=np.float64)
            else:
                arr = np.full_like(x, val, dtype=np.float64)
            expr_ns[name] = EvalResult(
                value=arr,
                y_unit=result.y_unit,
                y_unit_label=result.y_unit_label,
                y_label=result.y_label or name,
            )
            produced.append(AlignedTrace(
                registry_key=f"expr|{name}",
                legend_name=name,
                source_name=f"expr[{expr_def.expr_text}]",
                source_path=None,
                y_label=result.y_label or name,
                y_unit=result.y_unit,
                y_unit_label=result.y_unit_label,
                y=arr,
            ))

        elif isinstance(val, np.ndarray):
            expr_ns[name] = EvalResult(
                value=val,
                y_unit=result.y_unit,
                y_unit_label=result.y_unit_label,
                y_label=result.y_label or name,
            )
            produced.append(AlignedTrace(
                registry_key=f"expr|{name}",
                legend_name=name,
                source_name=f"expr[{expr_def.expr_text}]",
                source_path=None,
                y_label=result.y_label or name,
                y_unit=result.y_unit,
                y_unit_label=result.y_unit_label,
                y=val,
            ))

        elif isinstance(val, list):
            # Array-of-series: named name|1, name|2, ...
            sub_results: list[EvalResult] = []
            for i, sub_arr in enumerate(val, start=1):
                sub_name = f"{name}|{i}"
                sub_arr_np = np.asarray(sub_arr, dtype=np.float64)
                sub_er = EvalResult(
                    value=sub_arr_np,
                    y_unit=result.y_unit,
                    y_unit_label=result.y_unit_label,
                    y_label=f"{name}|{i}",
                )
                sub_results.append(sub_er)
                expr_ns[sub_name] = sub_er
                produced.append(AlignedTrace(
                    registry_key=f"expr|{sub_name}",
                    legend_name=sub_name,
                    source_name=f"expr[{expr_def.expr_text}]",
                    source_path=None,
                    y_label=f"{name}|{i}",
                    y_unit=result.y_unit,
                    y_unit_label=result.y_unit_label,
                    y=sub_arr_np,
                ))
            # Also store the whole array in expr_ns under the bare name
            expr_ns[name] = EvalResult(
                value=[er.value for er in sub_results],
                y_unit=result.y_unit,
                y_unit_label=result.y_unit_label,
                y_label=name,
            )

    return produced


def combine_plot_data(
    aligned_files: AlignedPlotData,
    expression_traces: list[AlignedTrace],
) -> AlignedPlotData:
    if not expression_traces:
        return aligned_files
    all_traces = [*aligned_files.traces, *expression_traces]
    y_units = {t.y_unit for t in all_traces}
    if len(y_units) > 2:
        raise ValueError("At most two distinct y-axis units are supported.")
    return AlignedPlotData(
        x_seconds=aligned_files.x_seconds,
        traces=all_traces,
        x_timestep_seconds=aligned_files.x_timestep_seconds,
        x_display_prefix=aligned_files.x_display_prefix,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_ref(a: str | None, b: str) -> str:
    if a is None:
        return b
    return f"{a}|{b}"


def _validate_strictly_increasing_x(x: np.ndarray, source_path: Path) -> None:
    diffs = np.diff(x)
    if diffs.size == 0:
        return
    if np.any(~np.isfinite(x)):
        raise ValueError(f"Non-finite x-axis values in {source_path}")
    if np.any(diffs <= 0):
        raise ValueError(f"x-axis data must be strictly increasing in {source_path}")


def _smallest_positive_dx(x_arrays: list[np.ndarray]) -> float:
    mins: list[float] = []
    for x in x_arrays:
        diffs = np.diff(x)
        positive = diffs[diffs > 0]
        if positive.size:
            mins.append(float(np.min(positive)))
    if not mins:
        raise ValueError("Could not determine global x-axis timestep")
    return min(mins)


def _uniform_grid(x_min: float, x_max: float, dt: float) -> np.ndarray:
    if dt <= 0:
        raise ValueError("Global timestep must be > 0")
    span = x_max - x_min
    if span < 0:
        raise ValueError("x_max must be >= x_min")
    ratio = span / dt if dt else 0.0
    steps = max(0, int(np.floor(ratio + 1e-12)))
    grid = x_min + (np.arange(steps + 1, dtype=np.float64) * dt)
    if grid.size == 0:
        return np.asarray([x_min], dtype=np.float64)
    if grid[-1] < x_max and not np.isclose(grid[-1], x_max):
        grid = np.append(grid, x_max)
    return grid


def _interpolate_onto_grid(x: np.ndarray, y: np.ndarray, x_grid: np.ndarray) -> np.ndarray:
    y_grid = np.full_like(x_grid, np.nan, dtype=np.float64)
    if x.size == 0:
        return y_grid
    tol = max(float(np.min(np.diff(x))) * 1e-6 if x.size > 1 else 0.0, 1e-15)
    mask = (x_grid >= (x[0] - tol)) & (x_grid <= (x[-1] + tol))
    if np.any(mask):
        y_grid[mask] = np.interp(x_grid[mask], x, y).astype(np.float64)
    return y_grid
