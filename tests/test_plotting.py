from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.plotting import write_multi_dygraphs_html
from time_plot.processing import AlignedPlotData, AlignedTrace


def test_write_multi_dygraphs_html_assigns_secondary_axis_for_second_y_type(tmp_path: Path) -> None:
    plot_data = AlignedPlotData(
        x_seconds=np.asarray([0.0, 1e-6, 2e-6]),
        traces=[
            AlignedTrace(
                dataset_name="f1",
                legend_name="Voltage",
                source_name="voltage",
                y_label="Voltage",
                y_unit="v",
                y=np.asarray([0.0, 1.0, 0.0]),
            ),
            AlignedTrace(
                dataset_name="f2",
                legend_name="Rate",
                source_name="rate",
                y_label="Rate",
                y_unit="v/s",
                y=np.asarray([1.0, 2.0, 3.0]),
            ),
        ],
    )
    out = tmp_path / "dual.html"
    write_multi_dygraphs_html(plot_data, out, title="dual")

    text = out.read_text(encoding="utf-8")
    assert 'const y2label = "Rate (' in text
    assert '"Rate": {"axis": "y2"}' in text
