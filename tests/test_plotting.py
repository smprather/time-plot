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
                registry_key="f1",
                legend_name="Voltage",
                source_name="voltage",
                source_path=None,
                y_label="Voltage",
                y_unit="v",
                y_unit_label="Voltage",
                y=np.asarray([0.0, 1.0, 0.0]),
            ),
            AlignedTrace(
                registry_key="f2",
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
    assert "Peak |y|" in text
    assert "RMS" in text
    assert "prox: 30" in text


def test_write_multi_html_uses_stepped_paths_for_non_logic_step_traces(tmp_path: Path) -> None:
    plot_data = AlignedPlotData(
        x_seconds=np.asarray([0.0, 1e-9, 2e-9]),
        traces=[
            AlignedTrace(
                registry_key="f1",
                legend_name="hold",
                source_name="sampled",
                source_path=None,
                y_label="hold",
                y_unit="v",
                y_unit_label="Voltage",
                y=np.asarray([0.0, 1.0, 0.0]),
                sample_mode="step",
            ),
        ],
    )
    out = tmp_path / "step.html"
    write_multi_html(plot_data, out, title="step")

    text = out.read_text(encoding="utf-8")
    assert 'sampleModes = ["step"]' in text
    assert "uPlot.paths.stepped({ align: 1 })" in text


def test_write_multi_html_uses_interval_paths_for_logic_traces(tmp_path: Path) -> None:
    plot_data = AlignedPlotData(
        x_seconds=np.asarray([0.0, 1e-9, 2e-9]),
        traces=[
            AlignedTrace(
                registry_key="f1",
                legend_name="clk",
                source_name="vcd",
                source_path=None,
                y_label="clk",
                y_unit="logic",
                y_unit_label="Logic",
                y=np.asarray([0.0, 1.0, 0.0]),
                sample_mode="step",
            ),
        ],
    )
    out = tmp_path / "logic.html"
    write_multi_html(plot_data, out, title="logic")

    text = out.read_text(encoding="utf-8")
    assert 'sampleModes = ["logic", "logic", "logic", "logic"]' in text
    assert "series[i].paths = logicIntervalPaths()" in text


def test_write_multi_html_stacks_logic_traces_into_lanes(tmp_path: Path) -> None:
    plot_data = AlignedPlotData(
        x_seconds=np.asarray([0.0, 1e-9]),
        traces=[
            AlignedTrace(
                registry_key="f1",
                legend_name="clk",
                source_name="vcd",
                source_path=None,
                y_label="clk",
                y_unit="logic",
                y_unit_label="Logic",
                y=np.asarray([0.0, 1.0]),
                sample_mode="step",
            ),
            AlignedTrace(
                registry_key="f2",
                legend_name="rst",
                source_name="vcd",
                source_path=None,
                y_label="rst",
                y_unit="logic",
                y_unit_label="Logic",
                y=np.asarray([1.0, 0.0]),
                sample_mode="step",
            ),
        ],
    )
    out = tmp_path / "logic_lanes.html"
    write_multi_html(plot_data, out, title="logic")

    text = out.read_text(encoding="utf-8")
    assert '"label": "", "logicLabels": ["rst", "clk"]' in text
    assert '"logicLabels": ["rst", "clk"]' in text
    assert 'const scales = {"x": {"time": false}, "y": {"range": [0, 2]}};' in text
    assert "[1.15, 1.85]" in text
    assert "[0.85, 0.15]" in text
    assert "Peak |y|" not in text
    assert "RMS" not in text
    assert '"legendShow": true' in text
    assert '"legendShow": false' in text
    assert '"logicGroup": "rst", "logicRole": "normal"' in text
    assert '"logicGroup": "rst", "logicRole": "z"' in text
    assert "const legendRowsBySeries = [null].concat(legendRows)" not in text
    assert "installLogicLegendGroups(uplot, logicGroups, legendRows)" in text
    assert "row.addEventListener(\"click\", function(event)" in text
    assert "u.batch(function()" in text
    assert "u.setSeries(seriesIdx, {show: show}, true)" in text
    assert 'legendRows[i].style.display = "none"' in text
    assert 'const legend = {"show": false}' not in text
    assert "dataIdx: function(u, seriesIdx, cursorIdx, xValue)" in text
    assert "return logicIntervalIndexForX(u.data[0], xValue, cursorIdx)" in text
    assert "prox: -1" in text


def test_write_multi_html_renders_logic_x_and_z_with_special_colors(tmp_path: Path) -> None:
    plot_data = AlignedPlotData(
        x_seconds=np.asarray([0.0, 1e-9, 2e-9, 3e-9, 4e-9, 5e-9]),
        traces=[
            AlignedTrace(
                registry_key="f1",
                legend_name="data",
                source_name="vcd",
                source_path=None,
                y_label="data",
                y_unit="logic",
                y_unit_label="Logic",
                y=np.asarray([1.0, np.nan, np.nan, np.nan, 0.0, 0.0]),
                sample_mode="step",
                logic_states=np.asarray(["1", "z", "z", "x", "0", "0"], dtype=np.str_),
            ),
        ],
    )
    out = tmp_path / "logic_x_z.html"
    write_multi_html(plot_data, out, title="logic")

    text = out.read_text(encoding="utf-8")
    assert '"stroke": "#f28e2b"' in text
    assert '"stroke": "#d62728"' in text
    assert '"points": {"show": false}' in text
    assert "series[group.main].value = function(u, value, seriesIdx, idx)" in text
    assert "return logicValueForGroupAtIndex(u, group, idx)" in text
    assert "function logicIntervalIndexForX(dataX, xValue, fallbackIdx)" in text
    assert 'if (zIdx != null && u.data[zIdx][idx] != null) return "Z";' in text
    assert 'if (xIdx != null && u.data[xIdx][idx] != null) return "X";' in text
    assert 'return y - Math.floor(y) >= 0.5 ? "1" : "0";' in text
    assert "[0.85, null, null, null, 0.15, 0.15]" in text
    assert "[null, 0.5, 0.5, null, null, null]" in text
    assert "[null, null, null, 0.15, null, null]" in text
    assert "[null, null, null, 0.85, null, null]" in text
