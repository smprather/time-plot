from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from time_plot.cli import cli


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_plot_command_supports_file_and_expression(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "expr_plot.html"
    sample_file = _repo_root() / "time_plot" / "example_data" / "sine.csv"

    result = runner.invoke(
        cli,
        [
            str(sample_file),
            "sum:expr[sine+sine]",
            "rate:expr[ddt(sum)]",
            "--output",
            str(output_html),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Expr:   sine+sine" in result.output
    assert "Expr:   ddt(sum)" in result.output
    assert output_html.exists()

    html = output_html.read_text(encoding="utf-8")
    assert "sum:sine+sine" in html
    assert "rate:ddt(sum)" in html


def test_plot_command_reports_expression_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    sample_file = _repo_root() / "time_plot" / "example_data" / "sine.csv"

    result = runner.invoke(
        cli,
        [str(sample_file), "bad:expr[missing+1]", "--output", str(tmp_path / "bad.html")],
    )

    assert result.exit_code != 0
    assert "Unknown dataset referenced in expression bad: missing" in result.output


def test_plot_command_auto_names_expressions(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "auto.html"
    sample_file = _repo_root() / "time_plot" / "example_data" / "sine.csv"

    result = runner.invoke(
        cli,
        [
            str(sample_file),
            "expr[sine+sine]",
            "--output",
            str(output_html),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Name:   e1" in result.output
    # Auto-named expressions use just the expression text as legend.
    assert "Legend: sine+sine" in result.output


def test_plot_command_expression_legend_with_user_name(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "named.html"
    sample_file = _repo_root() / "time_plot" / "example_data" / "sine.csv"

    result = runner.invoke(
        cli,
        [
            str(sample_file),
            "total:expr[sine+sine]",
            "--output",
            str(output_html),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Name:   total" in result.output
    # User-named expressions use name:expression as legend.
    assert "Legend: total:sine+sine" in result.output
