from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.plugin_system import discover_plugins, select_plugin


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plugin():
    plugins = discover_plugins(_repo_root() / "time_plot" / "plugins")
    assert plugins, "expected at least one plugin"
    plugin = next((p for p in plugins if p.plugin_name == "voltage-or-current-vs-time"), None)
    assert plugin is not None, "voltage-or-current-vs-time plugin not found"
    return plugin


def test_identify_voltage_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "time(us),voltage(mv)\n0,0\n1,1\n",
        encoding="utf-8",
    )
    assert _plugin().identify(csv_path) is True


def test_identify_current_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "time(ns),current(ma)\n0,0\n1,1\n",
        encoding="utf-8",
    )
    assert _plugin().identify(csv_path) is True


def test_identify_rejects_unknown_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "time(ns),power(w)\n0,0\n1,1\n",
        encoding="utf-8",
    )
    assert _plugin().identify(csv_path) is False


def test_parse_voltage_returns_base_units(tmp_path: Path) -> None:
    csv_path = tmp_path / "scaled.csv"
    csv_path.write_text(
        "time(ns),voltage(mv)\n0,0\n1000,1000\n",
        encoding="utf-8",
    )

    [series] = _plugin().parse(csv_path, {})

    assert series.x_unit == "s"
    assert series.y_unit == "v"
    assert series.y_unit_label == "Voltage"
    assert series.x_label == "Time"
    assert series.y_label == "scaled"
    assert series.name == "scaled"
    np.testing.assert_allclose(series.x, np.asarray([0.0, 1e-6]))
    np.testing.assert_allclose(series.y, np.asarray([0.0, 1.0]))


def test_parse_current_returns_base_units(tmp_path: Path) -> None:
    csv_path = tmp_path / "amps.csv"
    csv_path.write_text(
        "time(us),current(ma)\n0,0\n1,500\n",
        encoding="utf-8",
    )

    [series] = _plugin().parse(csv_path, {})

    assert series.x_unit == "s"
    assert series.y_unit == "a"
    assert series.y_unit_label == "Amps"
    assert series.name == "amps"
    np.testing.assert_allclose(series.x, np.asarray([0.0, 1e-6]))
    np.testing.assert_allclose(series.y, np.asarray([0.0, 0.5]))


def test_sample_file_is_recognized_and_selectable() -> None:
    sample_file = _repo_root() / "time_plot" / "example_data" / "sine.csv"
    plugins = discover_plugins(_repo_root() / "time_plot" / "plugins")
    plugin = select_plugin(sample_file, plugins)

    assert plugin.plugin_name == "voltage-or-current-vs-time"
