from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from time_plot.models import SeriesData
from time_plot.processing import (
    ExpressionSpec,
    InputFileSpec,
    LoadedDataset,
    align_loaded_datasets,
    combine_plot_data,
    evaluate_expressions,
    load_input_files,
)


def _loaded(
    *,
    legend: str,
    x: list[float],
    y: list[float],
    y_label: str = "Voltage",
    y_unit: str = "v",
) -> LoadedDataset:
    series = SeriesData(
        source_name="Test Source",
        x_label="Time",
        y_label=y_label,
        x_unit="s",
        y_unit=y_unit,
        x=np.asarray(x, dtype=np.float64),
        y=np.asarray(y, dtype=np.float64),
    )
    return LoadedDataset(
        dataset_name=legend,
        legend_name=legend,
        source_path=Path(f"{legend}.csv"),
        plugin_name="test-plugin",
        series=series,
    )


def test_align_loaded_datasets_uses_smallest_timestep_and_interpolates() -> None:
    a = _loaded(legend="a", x=[0.0, 1.0, 2.0], y=[0.0, 1.0, 2.0])
    b = _loaded(legend="b", x=[0.5, 2.5], y=[10.0, 30.0])

    aligned = align_loaded_datasets([a, b])

    np.testing.assert_allclose(aligned.x_seconds, np.asarray([0.0, 1.0, 2.0, 2.5]))
    assert len(aligned.traces) == 2
    np.testing.assert_allclose(aligned.traces[0].y[:3], np.asarray([0.0, 1.0, 2.0]))
    assert np.isnan(aligned.traces[0].y[3])
    assert np.isnan(aligned.traces[1].y[0])
    np.testing.assert_allclose(aligned.traces[1].y[1:3], np.asarray([15.0, 25.0]))
    np.testing.assert_allclose(aligned.traces[1].y[3], 30.0)


def test_align_loaded_datasets_rejects_non_monotonic_x() -> None:
    bad = _loaded(legend="bad", x=[0.0, 2.0, 1.0], y=[0.0, 1.0, 2.0])

    with pytest.raises(ValueError, match="strictly increasing"):
        align_loaded_datasets([bad])


def test_evaluate_expressions_supports_math_and_ddt() -> None:
    a = _loaded(legend="a", x=[0.0, 1.0, 2.0], y=[0.0, 1.0, 3.0])
    b = _loaded(legend="b", x=[0.0, 1.0, 2.0], y=[10.0, 20.0, 40.0])
    a.dataset_name = "f1"
    b.dataset_name = "f2"
    aligned = align_loaded_datasets([a, b])

    exprs = [
        ExpressionSpec(arg_position=3, dataset_name="sum", legend_name="sum", expression_text="f1+f2"),
        ExpressionSpec(arg_position=4, dataset_name="rate", legend_name="rate", expression_text="ddt(sum)"),
    ]
    traces = evaluate_expressions(aligned, exprs)
    combined = combine_plot_data(aligned, traces)

    assert len(traces) == 2
    sum_trace = next(t for t in combined.traces if t.dataset_name == "sum")
    rate_trace = next(t for t in combined.traces if t.dataset_name == "rate")
    np.testing.assert_allclose(sum_trace.y, np.asarray([10.0, 21.0, 43.0]))
    np.testing.assert_allclose(rate_trace.y, np.asarray([11.0, 11.0, 22.0]))
    assert rate_trace.y_unit == "v/s"


def test_evaluate_expressions_detects_circular_reference() -> None:
    base = _loaded(legend="a", x=[0.0, 1.0], y=[0.0, 1.0])
    base.dataset_name = "f1"
    aligned = align_loaded_datasets([base])

    exprs = [
        ExpressionSpec(arg_position=2, dataset_name="foo", legend_name="foo", expression_text="bar"),
        ExpressionSpec(arg_position=3, dataset_name="bar", legend_name="bar", expression_text="foo"),
    ]
    with pytest.raises(ValueError, match="Circular expression reference"):
        evaluate_expressions(aligned, exprs)


def test_evaluate_expressions_rejects_duplicate_expression_names() -> None:
    base = _loaded(legend="a", x=[0.0, 1.0], y=[0.0, 1.0])
    base.dataset_name = "f1"
    aligned = align_loaded_datasets([base])
    exprs = [
        ExpressionSpec(arg_position=2, dataset_name="dup", legend_name="dup", expression_text="f1"),
        ExpressionSpec(arg_position=3, dataset_name="dup", legend_name="dup2", expression_text="f1+1"),
    ]
    with pytest.raises(ValueError, match="Duplicate dataset name"):
        evaluate_expressions(aligned, exprs)


def test_evaluate_expressions_rejects_unknown_reference() -> None:
    base = _loaded(legend="a", x=[0.0, 1.0], y=[0.0, 1.0])
    base.dataset_name = "f1"
    aligned = align_loaded_datasets([base])
    exprs = [ExpressionSpec(arg_position=2, dataset_name="x", legend_name="x", expression_text="missing+1")]
    with pytest.raises(ValueError, match="Unknown dataset referenced"):
        evaluate_expressions(aligned, exprs)


def test_load_input_files_rejects_duplicate_dataset_names(tmp_path: Path) -> None:
    csv_path = tmp_path / "dummy.csv"
    csv_path.write_text("time(ns),voltage(v)\n0,0\n1,1\n", encoding="utf-8")

    class _DummyPlugin:
        plugin_name = "dummy"

        @staticmethod
        def identify(_path: Path) -> bool:
            return True

        @staticmethod
        def parse(_path: Path) -> SeriesData:
            return SeriesData(
                source_name="Dummy",
                x_label="Time",
                y_label="Voltage",
                x_unit="s",
                y_unit="v",
                x=np.asarray([0.0, 1.0]),
                y=np.asarray([0.0, 1.0]),
            )

    specs = [
        InputFileSpec(arg_position=1, path=csv_path, dataset_name="dup", cli_name="a"),
        InputFileSpec(arg_position=2, path=csv_path, dataset_name="dup", cli_name="b"),
    ]
    with pytest.raises(ValueError, match="Duplicate dataset name"):
        load_input_files(specs, [_DummyPlugin()])  # type: ignore[list-item]
