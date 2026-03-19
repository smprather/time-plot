from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.plugin_system import discover_plugins, select_plugin


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plugin():
    plugins = discover_plugins(_repo_root() / "time_plot" / "plugins")
    plugin = next((p for p in plugins if p.plugin_name == "cadence-dynamic-power-totalcurrent"), None)
    assert plugin is not None, "cadence-dynamic-power-totalcurrent plugin not found"
    return plugin


def test_identify_valid_file(tmp_path: Path) -> None:
    f = tmp_path / "VDD.peak.totalcurrent"
    f.write_text("    0\t  0.0000e+00\t 0.407291\n    1\t  1.0000e-11\t 0.407291\n", encoding="utf-8")
    assert _plugin().identify(f) is True


def test_identify_rejects_wrong_suffix(tmp_path: Path) -> None:
    f = tmp_path / "VDD.peak.csv"
    f.write_text("    0\t  0.0000e+00\t 0.407291\n", encoding="utf-8")
    assert _plugin().identify(f) is False


def test_identify_rejects_bad_first_line(tmp_path: Path) -> None:
    f = tmp_path / "bad.totalcurrent"
    f.write_text("time\tcurrent\n0\t1\n", encoding="utf-8")
    assert _plugin().identify(f) is False


def test_parse_returns_amps_and_seconds(tmp_path: Path) -> None:
    f = tmp_path / "VDD.peak.totalcurrent"
    f.write_text(
        "    0\t  0.0000e+00\t 0.1\n    1\t  1.0000e-09\t 0.2\n    2\t  2.0000e-09\t 0.3\n",
        encoding="utf-8",
    )

    [series] = _plugin().parse(f, {})

    assert series.x_unit == "s"
    assert series.y_unit == "a"
    assert series.y_unit_label == "Amps"
    assert series.x_label == "Time"
    assert series.name == "VDD.peak"
    assert series.y_label == "VDD.peak"
    np.testing.assert_allclose(series.x, np.asarray([0.0, 1e-9, 2e-9]))
    np.testing.assert_allclose(series.y, np.asarray([0.1, 0.2, 0.3]))


def test_example_file_is_recognized() -> None:
    example = _repo_root() / "time_plot" / "example_data" / "VDD.peak.totalcurrent"
    plugins = discover_plugins(_repo_root() / "time_plot" / "plugins")
    plugin = select_plugin(example, plugins)
    assert plugin.plugin_name == "cadence-dynamic-power-totalcurrent"


def test_example_file_parses() -> None:
    example = _repo_root() / "time_plot" / "example_data" / "VDD.peak.totalcurrent"
    [series] = _plugin().parse(example, {})
    assert series.x_unit == "s"
    assert series.y_unit == "a"
    assert len(series.x) > 0
    assert series.x[0] == 0.0
