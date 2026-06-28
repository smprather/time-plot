from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from time_plot.plugin_system import discover_plugins, select_plugin


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plugin():
    plugins = discover_plugins(_repo_root() / "time_plot" / "plugins")
    assert plugins, "expected at least one plugin"
    plugin = next((p for p in plugins if p.plugin_name == "vcd"), None)
    assert plugin is not None, "vcd plugin not found"
    return plugin


def _write_vcd(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_identify_recognizes_vcd(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        "$timescale 1 ns $end\n$enddefinitions $end\n",
    )

    assert _plugin().identify(vcd) is True


def test_identify_rejects_non_vcd(tmp_path: Path) -> None:
    txt = _write_vcd(tmp_path / "logic.txt", "$enddefinitions $end\n")

    assert _plugin().identify(txt) is False


def test_list_series_returns_scalar_hierarchy_and_skips_buses(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        """$timescale 1 ns $end
$scope module top $end
$scope module cpu $end
$var wire 1 ! clk $end
$var wire 8 " bus $end
$upscope $end
$upscope $end
$enddefinitions $end
""",
    )

    assert _plugin().list_series(vcd, {}) == ["top.cpu.clk"]


def test_parse_sample_file() -> None:
    sample = _repo_root() / "time_plot" / "example_data" / "logic.vcd"
    plugin = _plugin()

    assert plugin.identify(sample)
    series_list = plugin.parse(sample, {})

    assert [series.name for series in series_list] == ["top.clk", "top.reset_n", "top.data"]
    assert {series.sample_mode for series in series_list} == {"step"}
    assert {series.y_unit for series in series_list} == {"logic"}

    clk = next(series for series in series_list if series.name == "top.clk")
    np.testing.assert_allclose(clk.x, [0.0, 10e-9, 15e-9, 25e-9, 30e-9])
    np.testing.assert_allclose(clk.y, [0.0, 1.0, 0.0, 1.0, 0.0])

    reset_n = next(series for series in series_list if series.name == "top.reset_n")
    np.testing.assert_allclose(reset_n.x, [0.0, 5e-9, 30e-9])
    np.testing.assert_allclose(reset_n.y, [0.0, 1.0, 1.0])

    data = next(series for series in series_list if series.name == "top.data")
    np.testing.assert_allclose(data.x, [0.0, 15e-9, 20e-9, 25e-9, 30e-9])
    assert np.isnan(data.y[0])
    assert np.isnan(data.y[2])
    np.testing.assert_allclose(data.y[[1, 3, 4]], [1.0, 0.0, 0.0])
    assert data.logic_states is not None
    np.testing.assert_array_equal(data.logic_states, ["x", "1", "z", "0", "0"])


def test_parse_selected_filters_exact_series(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        """$timescale 1 ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 1 " rst $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
1"
$end
#10
1!
""",
    )

    series_list = _plugin().parse(vcd, {}, ["top.clk"])

    assert [series.name for series in series_list] == ["top.clk"]


def test_parse_timescale_conversion(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        """$timescale 10 ps $end
$var wire 1 ! clk $end
$enddefinitions $end
$dumpvars
0!
$end
#2
1!
""",
    )

    [series] = _plugin().parse(vcd, {})

    np.testing.assert_allclose(series.x, [0.0, 20e-12])


def test_parse_same_timestamp_keeps_final_value(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        """$timescale 1 ns $end
$var wire 1 ! clk $end
$enddefinitions $end
$dumpvars
0!
$end
#10
1!
0!
""",
    )

    [series] = _plugin().parse(vcd, {})

    np.testing.assert_allclose(series.x, [0.0, 10e-9])
    np.testing.assert_allclose(series.y, [0.0, 0.0])


def test_parse_requires_timescale(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        "$var wire 1 ! clk $end\n$enddefinitions $end\n",
    )

    with pytest.raises(ValueError, match="missing \\$timescale"):
        _plugin().parse(vcd, {})


def test_select_plugin_finds_vcd(tmp_path: Path) -> None:
    vcd = _write_vcd(
        tmp_path / "logic.vcd",
        "$timescale 1 ns $end\n$enddefinitions $end\n",
    )
    plugins = discover_plugins(_repo_root() / "time_plot" / "plugins")
    plugin = select_plugin(vcd, plugins)

    assert plugin.plugin_name == "vcd"
