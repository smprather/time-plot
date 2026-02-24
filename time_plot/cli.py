from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import click

from time_plot.plotting import write_multi_dygraphs_html
from time_plot.processing import InputFileSpec, align_loaded_datasets, load_input_files
from time_plot.plugin_system import discover_plugins
from time_plot.sample_data import write_example_data_files, write_voltage_time_sample_csv


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_plugins_dir() -> Path:
    return _repo_root() / "plugins"


def _default_sample_path() -> Path:
    return _repo_root() / "sample_data" / "sine.csv"


@dataclass(slots=True)
class CliSourceSpec:
    name: str | None
    raw: str
    kind: str  # "file" | "expr"


def parse_cli_source_spec(arg: str) -> CliSourceSpec:
    name: str | None = None
    raw = arg
    if ":" in arg:
        possible_name, remainder = arg.split(":", 1)
        if possible_name and remainder:
            name = possible_name
            raw = remainder

    kind = "expr" if raw.startswith("expr[") and raw.endswith("]") else "file"
    return CliSourceSpec(name=name, raw=raw, kind=kind)


@click.group()
def cli() -> None:
    """Plot time-series data via pluggable parsers."""


@cli.command()
@click.argument("sources", nargs=-1, type=str)
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
def plot(sources: tuple[str, ...], output_path: Path | None, plugins_dir: Path | None) -> None:
    """Parse a data file with the first matching plugin and write a Dygraphs HTML plot."""

    if not sources:
        source_specs = [CliSourceSpec(name=None, raw=str(_default_sample_path()), kind="file")]
    else:
        source_specs = [parse_cli_source_spec(value) for value in sources]

    expr_specs = [spec for spec in source_specs if spec.kind == "expr"]
    if expr_specs:
        raise click.ClickException("Expression inputs `expr[...]` are not implemented yet.")

    file_specs: list[InputFileSpec] = []
    for position, source_spec in enumerate(source_specs, start=1):
        source_file = Path(source_spec.raw)
        if not source_file.exists():
            msg = (
                f"Input file not found: {source_file}\n"
                "Run `python main.py sample-files` to generate example files."
            )
            raise click.ClickException(msg)
        file_specs.append(
            InputFileSpec(
                arg_position=position,
                path=source_file,
                cli_name=source_spec.name,
            ),
        )

    plugin_dir = plugins_dir or _default_plugins_dir()
    plugins = discover_plugins(plugin_dir)
    if not plugins:
        raise click.ClickException(f"No plugins found in {plugin_dir}")

    try:
        loaded = load_input_files(file_specs, plugins)
        aligned = align_loaded_datasets(loaded)
    except (LookupError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    final_output = output_path or (
        (_repo_root() / "plots" / f"{loaded[0].source_path.stem}.html")
        if len(loaded) == 1
        else (_repo_root() / "plots" / "combined.html")
    )
    title = loaded[0].series.source_name if len(loaded) == 1 else ", ".join(
        dataset.legend_name for dataset in loaded
    )
    written = write_multi_dygraphs_html(aligned, final_output, title=title)

    for dataset in loaded:
        click.echo(f"Plugin: {dataset.plugin_name}")
        click.echo(f"Input:  {dataset.source_path}")
        click.echo(f"Legend: {dataset.legend_name}")
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


@cli.command("sample-files")
@click.option(
    "-d",
    "--dir",
    "output_dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Output directory for generated example CSV files.",
)
def generate_sample_files(output_dir: Path | None) -> None:
    """Generate the seed example data files used for development/tests."""

    destination = output_dir or (_repo_root() / "sample_data")
    written = write_example_data_files(destination)
    for path in written:
        click.echo(f"Wrote example CSV: {path}")


def main() -> None:
    cli()
