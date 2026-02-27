from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.plugin_system import discover_plugins, select_plugin


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plugin():
    plugins = discover_plugins(_repo_root() / "plugins")
    assert plugins, "expected at least one plugin"
    plugin = next((p for p in plugins if p.plugin_name == "spice-pwl"), None)
    assert plugin is not None, "spice-pwl plugin not found"
    return plugin


def test_identify_recognizes_spice_pwl_file(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("i1 node1 0 pwl 0 0 10n 5m\n", encoding="utf-8")
    assert _plugin().identify(spi) is True


def test_identify_recognizes_voltage_source(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("v1 node1 0 pwl 0 0 10n 5m\n", encoding="utf-8")
    assert _plugin().identify(spi) is True


def test_identify_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("* comment\n\ni1 n1 0 pwl 0 0\n", encoding="utf-8")
    assert _plugin().identify(spi) is True


def test_identify_rejects_non_spice(tmp_path: Path) -> None:
    csv = tmp_path / "test.csv"
    csv.write_text("time(ns),voltage(v)\n0,0\n", encoding="utf-8")
    assert _plugin().identify(csv) is False


def test_identify_rejects_pwl_in_first_three_positions(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("pwl i1 node1 0 0 0\n", encoding="utf-8")
    assert _plugin().identify(spi) is False


def test_parse_inline_parens(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("i1 n1 0 pwl(0 0 10n 5m 20n 7m)\n", encoding="utf-8")
    [series] = _plugin().parse(spi, {})
    assert series.name == "i1"
    assert series.y_unit == "i"
    assert series.y_unit_label == "Current"
    np.testing.assert_allclose(series.x, [0.0, 10e-9, 20e-9])
    np.testing.assert_allclose(series.y, [0.0, 5e-3, 7e-3])


def test_parse_inline_no_parens(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("i2 n1 0 pwl 0 0 10n 5m 20n 7m\n", encoding="utf-8")
    [series] = _plugin().parse(spi, {})
    np.testing.assert_allclose(series.x, [0.0, 10e-9, 20e-9])
    np.testing.assert_allclose(series.y, [0.0, 5e-3, 7e-3])


def test_parse_line_continuation(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("i3 n1 0 pwl\n+ 0 0\n+ 10n 5m\n+ 20n 7m\n", encoding="utf-8")
    [series] = _plugin().parse(spi, {})
    np.testing.assert_allclose(series.x, [0.0, 10e-9, 20e-9])
    np.testing.assert_allclose(series.y, [0.0, 5e-3, 7e-3])


def test_parse_mixed_continuation(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("i4 n1 0 pwl 0 0 10n\n+ 5m 20n 7m\n", encoding="utf-8")
    [series] = _plugin().parse(spi, {})
    np.testing.assert_allclose(series.x, [0.0, 10e-9, 20e-9])
    np.testing.assert_allclose(series.y, [0.0, 5e-3, 7e-3])


def test_parse_voltage_source_unit(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("v1 n1 0 pwl 0 0 1u 3.3\n", encoding="utf-8")
    [series] = _plugin().parse(spi, {})
    assert series.y_unit == "v"
    assert series.y_unit_label == "Voltage"
    np.testing.assert_allclose(series.x, [0.0, 1e-6])
    np.testing.assert_allclose(series.y, [0.0, 3.3])


def test_parse_multiple_sources(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text(
        "i1 n1 0 pwl 0 0 10n 5m\n"
        "i2 n2 0 pwl 0 1m 10n 2m\n",
        encoding="utf-8",
    )
    series_list = _plugin().parse(spi, {})
    assert len(series_list) == 2
    assert series_list[0].name == "i1"
    assert series_list[1].name == "i2"


def test_parse_sample_file() -> None:
    sample = _repo_root() / "sample_data" / "spice_pwl_test1.spi"
    if not sample.exists():
        return
    plugin = _plugin()
    assert plugin.identify(sample)
    series_list = plugin.parse(sample, {})
    assert len(series_list) == 4
    for series in series_list:
        assert series.y_unit == "i"
        np.testing.assert_allclose(series.x, [0.0, 10e-9, 20e-9])
        np.testing.assert_allclose(series.y, [0.0, 5e-3, 7e-3])


def test_select_plugin_finds_spice_pwl(tmp_path: Path) -> None:
    spi = tmp_path / "test.spi"
    spi.write_text("v1 n1 0 pwl 0 0 1n 1\n", encoding="utf-8")
    plugins = discover_plugins(_repo_root() / "plugins")
    plugin = select_plugin(spi, plugins)
    assert plugin.plugin_name == "spice-pwl"
