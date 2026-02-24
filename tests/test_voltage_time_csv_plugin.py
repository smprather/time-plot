from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.plugin_system import discover_plugins, select_plugin


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plugin():
    plugins = discover_plugins(_repo_root() / "plugins")
    assert plugins, "expected at least one plugin"
    plugin = next((p for p in plugins if p.plugin_name == "voltage-vs-time-csv"), None)
    assert plugin is not None, "voltage-vs-time-csv plugin not found"
    return plugin


def test_identify_ignores_parenthetical_units(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "time(us),voltage(mv)\n0,0\n1,1\n",
        encoding="utf-8",
    )

    plugin = _plugin()
    assert plugin.identify(csv_path) is True


def test_parse_returns_base_units_and_converts_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "scaled.csv"
    csv_path.write_text(
        "time(ns),voltage(mv)\n0,0\n1000,1000\n",
        encoding="utf-8",
    )

    plugin = _plugin()
    series = plugin.parse(csv_path)

    assert series.x_unit == "s"
    assert series.y_unit == "v"
    assert series.x_label == "Time"
    assert series.y_label == "Voltage"
    np.testing.assert_allclose(series.x, np.asarray([0.0, 1e-6]))
    np.testing.assert_allclose(series.y, np.asarray([0.0, 1.0]))


def test_sample_file_is_recognized_and_selectable() -> None:
    sample_file = _repo_root() / "sample_data" / "sine.csv"
    plugins = discover_plugins(_repo_root() / "plugins")
    plugin = select_plugin(sample_file, plugins)

    assert plugin.plugin_name == "voltage-vs-time-csv"
