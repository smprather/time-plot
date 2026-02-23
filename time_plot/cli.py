from __future__ import annotations

from pathlib import Path

import click

from time_plot.plotting import write_dygraphs_html
from time_plot.plugin_system import discover_plugins, select_plugin
from time_plot.sample_data import write_voltage_time_sample_csv


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_plugins_dir() -> Path:
    return _repo_root() / "plugins"


def _default_sample_path() -> Path:
    return _repo_root() / "sample-data" / "voltage_time_sample.csv"


@click.group()
def cli() -> None:
    """Plot time-series data via pluggable parsers."""


@cli.command()
@click.argument(
    "input_file",
    required=False,
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="HTML output path. Defaults to plots/<input-stem>.html",
)
@click.option(
    "--plugins-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Directory containing parser plugins (.py files).",
)
def plot(input_file: Path | None, output_path: Path | None, plugins_dir: Path | None) -> None:
    """Parse a data file with the first matching plugin and write a Dygraphs HTML plot."""

    source_file = input_file or _default_sample_path()
    if not source_file.exists():
        msg = (
            f"Input file not found: {source_file}\n"
            "Run `python main.py sample` to generate the sample file."
        )
        raise click.ClickException(msg)

    plugin_dir = plugins_dir or _default_plugins_dir()
    plugins = discover_plugins(plugin_dir)
    if not plugins:
        raise click.ClickException(f"No plugins found in {plugin_dir}")

    try:
        plugin = select_plugin(source_file, plugins)
    except LookupError as exc:
        raise click.ClickException(str(exc)) from exc

    series = plugin.parse(source_file)
    final_output = output_path or (_repo_root() / "plots" / f"{source_file.stem}.html")
    written = write_dygraphs_html(series, final_output)

    click.echo(f"Plugin: {plugin.plugin_name}")
    click.echo(f"Input:  {source_file}")
    click.echo(f"Output: {written}")


@cli.command("sample")
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Where to write the sample CSV.",
)
@click.option(
    "--points",
    type=int,
    default=1000,
    show_default=True,
    help="Number of sample points to generate.",
)
def generate_sample(output_path: Path | None, points: int) -> None:
    """Write the development CSV sample: Voltage vs. Time CSV."""

    destination = output_path or _default_sample_path()
    written = write_voltage_time_sample_csv(destination, points=points)
    click.echo(f"Wrote sample CSV: {written}")


def main() -> None:
    cli()

