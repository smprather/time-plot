from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from time_plot.cli import cli


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sample(name: str = "sine.csv") -> Path:
    return _repo_root() / "time_plot" / "example_data" / name


def test_plot_command_file_and_expression(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "expr_plot.html"

    result = runner.invoke(cli, [
        "-f", str(_sample()),
        "-e", "total=sine+sine",
        "-e", "rate=ddt(total)",
        "--output", str(output_html),
        "--no-open-browser",
    ])

    assert result.exit_code == 0, result.output
    assert "total=sine+sine" in result.output
    assert "rate=ddt(total)" in result.output
    assert output_html.exists()


def test_plot_command_reports_expression_errors(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(cli, [
        "-f", str(_sample()),
        "-e", "bad=missing+1",
        "--output", str(tmp_path / "bad.html"),
        "--no-open-browser",
    ])

    assert result.exit_code != 0
    assert "matched no loaded series" in result.output or "ambiguous" in result.output


def test_plot_command_expression_name_in_output(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "named.html"

    result = runner.invoke(cli, [
        "-f", str(_sample()),
        "-e", "doubled=sine+sine",
        "--output", str(output_html),
        "--no-open-browser",
    ])

    assert result.exit_code == 0, result.output
    assert "doubled=sine+sine" in result.output


def test_plot_command_two_files_with_per_file_filters(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "dual.html"

    result = runner.invoke(cli, [
        "-f", str(_sample("sine.csv")),
        "-f", str(_sample("cosine.csv")),
        "--output", str(output_html),
        "--no-open-browser",
    ])

    assert result.exit_code == 0, result.output
    assert output_html.exists()


def test_plot_command_rms_scalar_expression(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "rms.html"

    result = runner.invoke(cli, [
        "-f", str(_sample()),
        "-e", "peak=rms(sine)",
        "--output", str(output_html),
        "--no-open-browser",
    ])

    assert result.exit_code == 0, result.output
    assert output_html.exists()
    # Scalar result should produce a horizontal line trace
    html = output_html.read_text(encoding="utf-8")
    assert "peak" in html


def test_plot_command_no_sources_uses_example(tmp_path: Path) -> None:
    runner = CliRunner()
    output_html = tmp_path / "example.html"

    result = runner.invoke(cli, [
        "--output", str(output_html),
        "--no-open-browser",
    ])

    assert result.exit_code == 0, result.output
    assert output_html.exists()
