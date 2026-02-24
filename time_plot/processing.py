from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData
from time_plot.plugin_system import ParserPlugin, select_plugin


@dataclass(slots=True)
class InputFileSpec:
    arg_position: int
    path: Path
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
    x_display_prefix: str | None = None


def load_input_files(
    input_files: list[InputFileSpec],
    plugins: list[ParserPlugin],
) -> list[LoadedDataset]:
    loaded: list[LoadedDataset] = []
    for spec in input_files:
        plugin = select_plugin(spec.path, plugins)
        series = plugin.parse(spec.path)
        dataset_name = spec.cli_name or f"f{spec.arg_position}"
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
                legend_name=dataset.legend_name,
                source_name=dataset.series.source_name,
                y_label=dataset.series.y_label,
                y_unit=dataset.series.y_unit,
                y=y_grid,
                y_display_prefix=dataset.series.y_display_prefix,
            ),
        )

    y_types = {(trace.y_label, trace.y_unit) for trace in traces}
    if len(y_types) > 2:
        msg = "At most two distinct y-axis types are supported."
        raise ValueError(msg)

    return AlignedPlotData(
        x_seconds=x_grid,
        traces=traces,
        x_display_prefix=datasets[0].series.x_display_prefix,
    )


def _legend_name(spec: InputFileSpec, series: SeriesData) -> str:
    if spec.cli_name:
        return spec.cli_name
    if series.y_label:
        return series.y_label
    if spec.path.name:
        return spec.path.stem
    return f"f{spec.arg_position}"


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
    steps = max(0, int(np.ceil((span / dt) - 1e-12)))
    grid = x_min + (np.arange(steps + 1, dtype=np.float64) * dt)
    if grid.size == 0:
        return np.asarray([x_min], dtype=np.float64)
    if grid[-1] < x_max and not np.isclose(grid[-1], x_max):
        grid = np.append(grid, grid[-1] + dt)
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

