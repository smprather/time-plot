from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.plotting import write_multi_html
from time_plot.processing import AlignedPlotData, AlignedTrace


def test_write_multi_html_assigns_secondary_axis_for_second_y_unit(tmp_path: Path) -> None:
    plot_data = AlignedPlotData(
        x_seconds=np.asarray([0.0, 1e-6, 2e-6]),
        traces=[
            AlignedTrace(
                dataset_name="f1",
                legend_name="Voltage",
                source_name="voltage",
                source_path=None,
                y_label="Voltage",
                y_unit="v",
                y_unit_label="Voltage",
                y=np.asarray([0.0, 1.0, 0.0]),
            ),
            AlignedTrace(
                dataset_name="f2",
                legend_name="Rate",
                source_name="rate",
                source_path=None,
                y_label="Rate",
                y_unit="v/s",
                y_unit_label="v/s",
                y=np.asarray([1.0, 2.0, 3.0]),
            ),
        ],
    )
    out = tmp_path / "dual.html"
    write_multi_html(plot_data, out, title="dual")

    text = out.read_text(encoding="utf-8")
    assert '"scale": "y2"' in text
    assert "v/s" in text
