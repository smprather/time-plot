from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from time_plot.models import SeriesData
from time_plot.processing import LoadedDataset, align_loaded_datasets


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

    np.testing.assert_allclose(aligned.x_seconds, np.asarray([0.0, 1.0, 2.0, 3.0]))
    assert len(aligned.traces) == 2
    np.testing.assert_allclose(aligned.traces[0].y[:3], np.asarray([0.0, 1.0, 2.0]))
    assert np.isnan(aligned.traces[0].y[3])
    assert np.isnan(aligned.traces[1].y[0])
    np.testing.assert_allclose(aligned.traces[1].y[1:3], np.asarray([15.0, 25.0]))
    assert np.isnan(aligned.traces[1].y[3])


def test_align_loaded_datasets_rejects_non_monotonic_x() -> None:
    bad = _loaded(legend="bad", x=[0.0, 2.0, 1.0], y=[0.0, 1.0, 2.0])

    with pytest.raises(ValueError, match="strictly increasing"):
        align_loaded_datasets([bad])
