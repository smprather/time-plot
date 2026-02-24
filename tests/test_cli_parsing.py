from __future__ import annotations

from time_plot.cli import parse_cli_source_spec


def test_parse_cli_source_spec_file_and_named_file() -> None:
    spec = parse_cli_source_spec("foo.csv")
    assert spec.kind == "file"
    assert spec.name is None
    assert spec.raw == "foo.csv"

    named = parse_cli_source_spec("data1:/tmp/foo.csv")
    assert named.kind == "file"
    assert named.name == "data1"
    assert named.raw == "/tmp/foo.csv"


def test_parse_cli_source_spec_expression() -> None:
    spec = parse_cli_source_spec("sum:expr[f1+f2]")
    assert spec.kind == "expr"
    assert spec.name == "sum"
    assert spec.raw == "expr[f1+f2]"
