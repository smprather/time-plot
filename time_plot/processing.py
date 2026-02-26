from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ast

import numpy as np

from time_plot.models import SeriesData
from time_plot.plugin_system import ParserPlugin, select_plugin


@dataclass(slots=True)
class InputFileSpec:
    arg_position: int
    path: Path
    dataset_name: str
    cli_name: str | None = None


@dataclass(slots=True)
class LoadedDataset:
    dataset_name: str
    legend_name: str
    source_path: Path
    plugin_name: str
    series: SeriesData


@dataclass(slots=True)
class AlignedTrace:
    dataset_name: str
    legend_name: str
    source_name: str
    y_label: str
    y_unit: str
    y: np.ndarray
    y_display_prefix: str | None = None


@dataclass(slots=True)
class AlignedPlotData:
    x_seconds: np.ndarray
    traces: list[AlignedTrace]
    x_timestep_seconds: float | None = None
    x_display_prefix: str | None = None


@dataclass(slots=True)
class ExpressionSpec:
    arg_position: int
    dataset_name: str
    legend_name: str
    expression_text: str


def load_input_files(
    input_files: list[InputFileSpec],
    plugins: list[ParserPlugin],
) -> list[LoadedDataset]:
    loaded: list[LoadedDataset] = []
    seen_dataset_names: set[str] = set()
    for spec in input_files:
        if spec.dataset_name in seen_dataset_names:
            msg = f"Duplicate dataset name: {spec.dataset_name}"
            raise ValueError(msg)
        seen_dataset_names.add(spec.dataset_name)
        plugin = select_plugin(spec.path, plugins)
        series = plugin.parse(spec.path)
        dataset_name = spec.dataset_name
        legend_name = _legend_name(spec, series)
        loaded.append(
            LoadedDataset(
                dataset_name=dataset_name,
                legend_name=legend_name,
                source_path=spec.path,
                plugin_name=plugin.plugin_name,
                series=series,
            ),
        )
    return loaded


def align_loaded_datasets(datasets: list[LoadedDataset]) -> AlignedPlotData:
    if not datasets:
        msg = "No datasets to align"
        raise ValueError(msg)

    for dataset in datasets:
        _validate_strictly_increasing_x(dataset.series.x, dataset.source_path)

    x_arrays = [dataset.series.x for dataset in datasets]
    dt = _smallest_positive_dx(x_arrays)
    x_min = min(float(arr[0]) for arr in x_arrays)
    x_max = max(float(arr[-1]) for arr in x_arrays)
    x_grid = _uniform_grid(x_min, x_max, dt)

    traces: list[AlignedTrace] = []
    for dataset in datasets:
        y_grid = _interpolate_onto_grid(dataset.series.x, dataset.series.y, x_grid)
        traces.append(
            AlignedTrace(
                dataset_name=dataset.dataset_name,
                legend_name=dataset.legend_name,
                source_name=dataset.series.source_name,
                y_label=dataset.series.y_label,
                y_unit=dataset.series.y_unit,
                y=y_grid,
                y_display_prefix=dataset.series.y_display_prefix,
            ),
        )

    y_units = {trace.y_unit for trace in traces}
    if len(y_units) > 2:
        msg = "At most two distinct y-axis units are supported."
        raise ValueError(msg)

    return AlignedPlotData(
        x_seconds=x_grid,
        traces=traces,
        x_timestep_seconds=dt,
        x_display_prefix=datasets[0].series.x_display_prefix,
    )


def evaluate_expressions(
    base_plot_data: AlignedPlotData,
    expressions: list[ExpressionSpec],
) -> list[AlignedTrace]:
    if not expressions:
        return []

    if not base_plot_data.traces:
        msg = "Expressions require at least one file-backed dataset."
        raise ValueError(msg)

    values_by_name: dict[str, np.ndarray] = {}
    trace_meta_by_name: dict[str, AlignedTrace] = {}
    for trace in base_plot_data.traces:
        values_by_name[trace.dataset_name] = trace.y.copy()
        trace_meta_by_name[trace.dataset_name] = trace

    for expr in expressions:
        if expr.dataset_name in values_by_name:
            msg = f"Duplicate dataset name: {expr.dataset_name}"
            raise ValueError(msg)

    expr_by_name: dict[str, ExpressionSpec] = {}
    for expr in expressions:
        if expr.dataset_name in expr_by_name:
            msg = f"Duplicate dataset name: {expr.dataset_name}"
            raise ValueError(msg)
        expr_by_name[expr.dataset_name] = expr
    _validate_expression_names(expr_by_name, values_by_name.keys())
    eval_order = _expression_eval_order(expr_by_name, set(values_by_name))

    produced: list[AlignedTrace] = []
    for name in eval_order:
        expr = expr_by_name[name]
        result_values, result_meta = _eval_expression(
            expr.expression_text,
            x_seconds=base_plot_data.x_seconds,
            values_by_name=values_by_name,
            trace_meta_by_name=trace_meta_by_name,
        )
        values_by_name[name] = result_values
        trace_meta = AlignedTrace(
            dataset_name=expr.dataset_name,
            legend_name=expr.legend_name,
            source_name=f"expr[{expr.expression_text}]",
            y_label=result_meta.y_label,
            y_unit=result_meta.y_unit,
            y=result_values,
            y_display_prefix=None,
        )
        trace_meta_by_name[name] = trace_meta
        produced.append(trace_meta)

    return produced


def combine_plot_data(
    aligned_files: AlignedPlotData,
    expression_traces: list[AlignedTrace],
) -> AlignedPlotData:
    if not expression_traces:
        return aligned_files
    return AlignedPlotData(
        x_seconds=aligned_files.x_seconds,
        traces=[*aligned_files.traces, *expression_traces],
        x_timestep_seconds=aligned_files.x_timestep_seconds,
        x_display_prefix=aligned_files.x_display_prefix,
    )


def _legend_name(spec: InputFileSpec, series: SeriesData) -> str:
    if spec.cli_name:
        return spec.cli_name
    if series.y_label:
        return series.y_label
    if spec.path.name:
        return spec.path.stem
    return spec.dataset_name


def default_dataset_name(arg_position: int) -> str:
    return f"f{arg_position}"


def expression_legend_name(cli_name: str | None, expression_text: str) -> str:
    if cli_name:
        return cli_name
    return expression_text.replace(" ", "")


def _validate_strictly_increasing_x(x: np.ndarray, source_path: Path) -> None:
    diffs = np.diff(x)
    if diffs.size == 0:
        return
    if np.any(~np.isfinite(x)):
        msg = f"Non-finite x-axis values in {source_path}"
        raise ValueError(msg)
    if np.any(diffs <= 0):
        msg = f"x-axis data must be strictly increasing in {source_path}"
        raise ValueError(msg)


def _smallest_positive_dx(x_arrays: list[np.ndarray]) -> float:
    mins: list[float] = []
    for x in x_arrays:
        diffs = np.diff(x)
        positive = diffs[diffs > 0]
        if positive.size:
            mins.append(float(np.min(positive)))
    if not mins:
        msg = "Could not determine global x-axis timestep"
        raise ValueError(msg)
    return min(mins)


def _uniform_grid(x_min: float, x_max: float, dt: float) -> np.ndarray:
    if dt <= 0:
        msg = "Global timestep must be > 0"
        raise ValueError(msg)
    span = x_max - x_min
    if span < 0:
        msg = "x_max must be >= x_min"
        raise ValueError(msg)

    # Deterministic grid anchored at global minimum x using the smallest source dx.
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


@dataclass(slots=True)
class _ExprValue:
    values: np.ndarray
    finite_mask: np.ndarray
    y_label: str
    y_unit: str


def _validate_expression_names(
    expr_by_name: dict[str, ExpressionSpec],
    base_names: object,
) -> None:
    base_name_set = set(base_names)
    for expr in expr_by_name.values():
        if not expr.dataset_name.isidentifier():
            msg = f"Invalid dataset name for expression: {expr.dataset_name}"
            raise ValueError(msg)
        if expr.dataset_name in base_name_set:
            msg = f"Duplicate dataset name: {expr.dataset_name}"
            raise ValueError(msg)


def _expression_eval_order(
    expr_by_name: dict[str, ExpressionSpec],
    base_names: set[str],
) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    order: list[str] = []

    refs_cache: dict[str, set[str]] = {}

    def refs_for(name: str) -> set[str]:
        if name not in refs_cache:
            refs_cache[name] = _referenced_names(expr_by_name[name].expression_text)
        return refs_cache[name]

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            msg = f"Circular expression reference detected involving {name}"
            raise ValueError(msg)
        visiting.add(name)
        for ref in refs_for(name):
            if ref in expr_by_name:
                visit(ref)
            elif ref not in base_names:
                msg = f"Unknown dataset referenced in expression {name}: {ref}"
                raise ValueError(msg)
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for name in expr_by_name:
        visit(name)
    return order


def _referenced_names(expression_text: str) -> set[str]:
    root = ast.parse(expression_text, mode="eval")
    refs: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
            refs.add(node.id)

        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            if not isinstance(node.func, ast.Name):
                msg = "Unsupported function syntax in expression"
                raise ValueError(msg)
            self.generic_visit(node)

    Visitor().visit(root)
    return refs - {"average", "rms", "abs", "ddt"}


def _eval_expression(
    expression_text: str,
    *,
    x_seconds: np.ndarray,
    values_by_name: dict[str, np.ndarray],
    trace_meta_by_name: dict[str, AlignedTrace],
) -> tuple[np.ndarray, _ExprValue]:
    root = ast.parse(expression_text, mode="eval")
    value = _eval_expr_node(root.body, x_seconds, values_by_name, trace_meta_by_name)
    output = value.values.copy()
    output[~value.finite_mask] = np.nan
    return output, _ExprValue(
        values=output,
        finite_mask=value.finite_mask,
        y_label=value.y_label,
        y_unit=value.y_unit,
    )


def _eval_expr_node(
    node: ast.AST,
    x_seconds: np.ndarray,
    values_by_name: dict[str, np.ndarray],
    trace_meta_by_name: dict[str, AlignedTrace],
) -> _ExprValue:
    if isinstance(node, ast.Name):
        if node.id not in values_by_name:
            msg = f"Unknown dataset: {node.id}"
            raise ValueError(msg)
        arr = values_by_name[node.id]
        trace = trace_meta_by_name[node.id]
        finite = np.isfinite(arr)
        return _ExprValue(
            values=arr.copy(),
            finite_mask=finite,
            y_label=trace.y_label,
            y_unit=trace.y_unit,
        )

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        arr = np.full_like(x_seconds, float(node.value), dtype=np.float64)
        return _ExprValue(
            values=arr,
            finite_mask=np.ones_like(arr, dtype=bool),
            y_label="Expression",
            y_unit="1",
        )

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        inner = _eval_expr_node(node.operand, x_seconds, values_by_name, trace_meta_by_name)
        values = inner.values if isinstance(node.op, ast.UAdd) else -inner.values
        return _ExprValue(values=values, finite_mask=inner.finite_mask.copy(), y_label=inner.y_label, y_unit=inner.y_unit)

    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _eval_expr_node(node.left, x_seconds, values_by_name, trace_meta_by_name)
        right = _eval_expr_node(node.right, x_seconds, values_by_name, trace_meta_by_name)
        mask = left.finite_mask & right.finite_mask
        values = np.full_like(x_seconds, np.nan, dtype=np.float64)
        left_v = np.where(mask, left.values, np.nan)
        right_v = np.where(mask, right.values, np.nan)
        if isinstance(node.op, ast.Add):
            if left.y_unit != right.y_unit:
                msg = f"Cannot add datasets with different units: {left.y_unit} and {right.y_unit}"
                raise ValueError(msg)
            values = left_v + right_v
            y_label, y_unit = left.y_label, left.y_unit
        elif isinstance(node.op, ast.Sub):
            if left.y_unit != right.y_unit:
                msg = f"Cannot subtract datasets with different units: {left.y_unit} and {right.y_unit}"
                raise ValueError(msg)
            values = left_v - right_v
            y_label, y_unit = left.y_label, left.y_unit
        elif isinstance(node.op, ast.Mult):
            values = left_v * right_v
            y_label, y_unit = "Expression", _combine_units_mul(left.y_unit, right.y_unit)
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                values = left_v / right_v
            mask = mask & np.isfinite(values)
            y_label, y_unit = "Expression", _combine_units_div(left.y_unit, right.y_unit)
        values[~mask] = np.nan
        return _ExprValue(values=values, finite_mask=mask, y_label=y_label, y_unit=y_unit)

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn_name = node.func.id
        if len(node.args) != 1:
            msg = f"Function {fn_name}() expects exactly one argument"
            raise ValueError(msg)
        arg = _eval_expr_node(node.args[0], x_seconds, values_by_name, trace_meta_by_name)
        if fn_name == "average":
            finite_vals = arg.values[arg.finite_mask]
            mean_val = float(np.mean(finite_vals)) if finite_vals.size else np.nan
            values = np.full_like(x_seconds, np.nan, dtype=np.float64)
            values[arg.finite_mask] = mean_val
            return _ExprValue(values=values, finite_mask=arg.finite_mask.copy(), y_label=arg.y_label, y_unit=arg.y_unit)
        if fn_name == "rms":
            finite_vals = arg.values[arg.finite_mask]
            rms_val = float(np.sqrt(np.mean(finite_vals**2))) if finite_vals.size else np.nan
            values = np.full_like(x_seconds, np.nan, dtype=np.float64)
            values[arg.finite_mask] = rms_val
            return _ExprValue(values=values, finite_mask=arg.finite_mask.copy(), y_label=arg.y_label, y_unit=arg.y_unit)
        if fn_name == "abs":
            values = np.full_like(x_seconds, np.nan, dtype=np.float64)
            values[arg.finite_mask] = np.abs(arg.values[arg.finite_mask])
            return _ExprValue(values=values, finite_mask=arg.finite_mask.copy(), y_label=arg.y_label, y_unit=arg.y_unit)
        if fn_name == "ddt":
            values, mask = _ddt(arg.values, arg.finite_mask, x_seconds)
            return _ExprValue(values=values, finite_mask=mask, y_label=arg.y_label, y_unit=_ddt_unit(arg.y_unit))
        msg = f"Unsupported function in expression: {fn_name}"
        raise ValueError(msg)

    msg = "Unsupported expression syntax"
    raise ValueError(msg)


def _ddt(values: np.ndarray, finite_mask: np.ndarray, x_seconds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    out = np.full_like(values, np.nan, dtype=np.float64)
    mask = np.zeros_like(finite_mask, dtype=bool)
    if values.size < 2:
        return out, mask
    dx = np.diff(x_seconds)
    valid_pairs = finite_mask[:-1] & finite_mask[1:] & (dx > 0)
    deriv = np.full(values.size - 1, np.nan, dtype=np.float64)
    deriv[valid_pairs] = (values[1:][valid_pairs] - values[:-1][valid_pairs]) / dx[valid_pairs]
    out[1:] = deriv
    mask[1:] = valid_pairs
    # First point equals second point when available.
    if mask.size > 1 and mask[1]:
        out[0] = out[1]
        mask[0] = True
    return out, mask


def _ddt_unit(unit: str) -> str:
    if unit in {"", "1"}:
        return "1/s"
    return f"{unit}/s"


def _combine_units_mul(left: str, right: str) -> str:
    if left == "1":
        return right
    if right == "1":
        return left
    return f"{left}*{right}"


def _combine_units_div(left: str, right: str) -> str:
    if right == "1":
        return left
    if left == "1":
        return f"1/{right}"
    return f"{left}/{right}"
