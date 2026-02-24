from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from time_plot.cli import cli


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_sample_files_command_writes_expected_files(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["sample-files", "--dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "sine.csv").exists()
    assert (tmp_path / "cosine.csv").exists()


def test_plot_command_supports_file_and_expression(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "expr_plot.html"
    sample_file = _repo_root() / "sample_data" / "sine.csv"

    result = runner.invoke(
        cli,
        [
            "plot",
            str(sample_file),
            "sum:expr[f1+f1]",
            "rate:expr[ddt(sum)]",
            "--output",
            str(output_html),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Expr:   f1+f1" in result.output
    assert "Expr:   ddt(sum)" in result.output
    assert output_html.exists()

    html = output_html.read_text(encoding="utf-8")
    assert '"sum"' in html
    assert '"rate"' in html


def test_plot_command_reports_expression_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    sample_file = _repo_root() / "sample_data" / "sine.csv"

    result = runner.invoke(
        cli,
        ["plot", str(sample_file), "bad:expr[missing+1]", "--output", str(tmp_path / "bad.html")],
    )

    assert result.exit_code != 0
    assert "Unknown dataset referenced in expression bad: missing" in result.output
