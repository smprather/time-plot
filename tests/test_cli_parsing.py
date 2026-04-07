from __future__ import annotations

import pytest
from click.testing import CliRunner

from time_plot.cli import _build_file_groups, _parse_expr_arg
from time_plot.processing import ExpressionDef


def test_build_file_groups_single_file(tmp_path):
    f = tmp_path / "signal.csv"
    f.write_text("time(ns),voltage(v)\n0,0\n1,1\n")
    groups, exprs = _build_file_groups(["-f", str(f)])
    assert len(groups) == 1
    assert groups[0].files == [f]
    assert groups[0].glob_filter is None
    assert groups[0].regex_filter is None
    assert exprs == []


def test_build_file_groups_filter_binds_to_preceding_files(tmp_path):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    f1.write_text("x")
    f2.write_text("x")
    groups, _ = _build_file_groups(["-f", str(f1), "-f", str(f2), "-F", "rtr*"])
    assert len(groups) == 1
    assert set(groups[0].files) == {f1, f2}
    assert groups[0].glob_filter == "rtr*"


def test_build_file_groups_per_file_filters(tmp_path):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    f1.write_text("x")
    f2.write_text("x")
    groups, _ = _build_file_groups([
        "-f", str(f1), "-F", "rtr*",
        "-f", str(f2), "-F", "cts*",
    ])
    assert len(groups) == 2
    assert groups[0].files == [f1]
    assert groups[0].glob_filter == "rtr*"
    assert groups[1].files == [f2]
    assert groups[1].glob_filter == "cts*"


def test_build_file_groups_trailing_file_no_filter(tmp_path):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    f1.write_text("x")
    f2.write_text("x")
    groups, _ = _build_file_groups([
        "-f", str(f1), "-F", "rtr*",
        "-f", str(f2),
    ])
    assert len(groups) == 2
    assert groups[1].glob_filter is None


def test_build_file_groups_regex_filter(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x")
    groups, _ = _build_file_groups(["-f", str(f), "-R", r"^rtr_\d+"])
    assert groups[0].regex_filter == r"^rtr_\d+"
    assert groups[0].glob_filter is None


def test_build_file_groups_expressions(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x")
    groups, exprs = _build_file_groups(["-f", str(f), "-e", "total=sum(*|foo)"])
    assert len(exprs) == 1
    assert exprs[0].name == "total"
    assert exprs[0].expr_text == "sum(*|foo)"


def test_parse_expr_arg_valid():
    out: list[ExpressionDef] = []
    _parse_expr_arg("peak=rms(foo)", out)
    assert len(out) == 1
    assert out[0].name == "peak"
    assert out[0].expr_text == "rms(foo)"


def test_parse_expr_arg_missing_equals():
    import click
    out: list[ExpressionDef] = []
    with pytest.raises(click.ClickException, match="form 'name=expr'"):
        _parse_expr_arg("noequals", out)


def test_parse_expr_arg_invalid_name():
    import click
    out: list[ExpressionDef] = []
    with pytest.raises(click.ClickException, match="simple identifier"):
        _parse_expr_arg("123bad=foo", out)


def test_build_file_groups_missing_file():
    import click
    with pytest.raises(click.ClickException, match="not found"):
        _build_file_groups(["-f", "/nonexistent/path/file.csv"])
