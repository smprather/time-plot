from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import webbrowser

import rich_click as click

from time_plot.plotting import write_multi_html
from time_plot.plugin_system import discover_plugins
from time_plot.processing import (
    ExpressionSpec,
    InputFileSpec,
    align_loaded_datasets,
    combine_plot_data,
    evaluate_expressions,
    expression_legend_name,
    load_input_files,
)


def _default_plugins_dir() -> Path:
    return Path(__file__).parent / "plugins"


def _default_example_path() -> Path:
    return Path(__file__).parent / "example_data" / "sine.csv"


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
        is_windows_drive = len(possible_name) == 1 and possible_name.isalpha() and remainder.startswith(("\\", "/"))
        if possible_name and remainder and not is_windows_drive:
            name = possible_name
            raw = remainder

    kind = "expr" if raw.startswith("expr[") and raw.endswith("]") else "file"
    return CliSourceSpec(name=name, raw=raw, kind=kind)


@click.command()
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
@click.option(
    "--parser-options",
    "parser_options_raw",
    type=str,
    default=None,
    help="Comma-separated key=value pairs passed to parser plugins.",
)
@click.option(
    "--open-browser/--no-open-browser",
    default=True,
    help="Open the output HTML in the default browser after writing (default: true).",
)
def cli(
    sources: tuple[str, ...],
    output_path: Path | None,
    plugins_dir: Path | None,
    parser_options_raw: str | None,
    open_browser: bool,
) -> None:
    """Plot time-series data via pluggable parsers."""

    if not sources:
        source_specs = [
            CliSourceSpec(name=None, raw=str(_default_example_path()), kind="file")
        ]
    else:
        source_specs = [parse_cli_source_spec(value) for value in sources]

    file_specs: list[InputFileSpec] = []
    expression_specs: list[ExpressionSpec] = []
    seen_source_names: set[str] = set()
    expr_counter = 0
    for position, source_spec in enumerate(source_specs, start=1):
        if source_spec.kind == "expr":
            expression_text = source_spec.raw[5:-1]
            if source_spec.name:
                if source_spec.name == "expr":
                    raise click.ClickException(
                        "'expr' is a reserved data_source name and cannot be used."
                    )
                dataset_name = source_spec.name
            else:
                expr_counter += 1
                dataset_name = f"e{expr_counter}"
            expression_specs.append(
                ExpressionSpec(
                    arg_position=position,
                    dataset_name=dataset_name,
                    legend_name=expression_legend_name(dataset_name, expression_text),
                    expression_text=expression_text,
                ),
            )
            continue

        source_file = Path(source_spec.raw)
        if not source_file.exists():
            msg = (
                f"Input file not found: {source_file}\n"
                "Run `scripts/generate_example_data.py` to generate example files."
            )
            raise click.ClickException(msg)

        if source_spec.name:
            if source_spec.name == "expr":
                raise click.ClickException(
                    "'expr' is a reserved data_source name and cannot be used."
                )
            data_source_name = source_spec.name
        else:
            data_source_name = source_file.stem

        # Name-bump auto-generated data_source_names on conflict; error for CLI names.
        if data_source_name in seen_source_names:
            if source_spec.name:
                raise click.ClickException(
                    f"Duplicate data_source name: {data_source_name}"
                )
            counter = 1
            while f"{data_source_name}_{counter}" in seen_source_names:
                counter += 1
            data_source_name = f"{data_source_name}_{counter}"
        seen_source_names.add(data_source_name)

        file_specs.append(
            InputFileSpec(
                arg_position=position,
                path=source_file,
                data_source_name=data_source_name,
                cli_name=source_spec.name,
            ),
        )

    parser_options: dict[str, str] = {}
    if parser_options_raw:
        for pair in parser_options_raw.split(","):
            if "=" not in pair:
                raise click.ClickException(
                    f"Invalid parser option (missing '='): {pair}"
                )
            key, value = pair.split("=", 1)
            parser_options[key.strip()] = value.strip()

    plugin_dir = plugins_dir or _default_plugins_dir()
    plugins = discover_plugins(plugin_dir)
    if not plugins:
        raise click.ClickException(f"No plugins found in {plugin_dir}")

    try:
        loaded = load_input_files(file_specs, plugins, parser_options=parser_options)
        aligned_files = align_loaded_datasets(loaded)
        expr_traces = evaluate_expressions(aligned_files, expression_specs)
        aligned = combine_plot_data(aligned_files, expr_traces)
    except (LookupError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    final_output = output_path or (
        (Path.cwd() / "plots" / f"{loaded[0].source_path.stem}.html")
        if len(loaded) == 1
        else (Path.cwd() / "plots" / "combined.html")
    )
    title_parts = [dataset.legend_name for dataset in loaded] + [
        expr.legend_name for expr in expression_specs
    ]
    title = (
        loaded[0].series.source_name
        if len(title_parts) == 1 and loaded
        else ", ".join(title_parts)
    )
    written = write_multi_html(aligned, final_output, title=title)

    for dataset in loaded:
        click.echo(f"Plugin: {dataset.plugin_name}")
        click.echo(f"Input:  {dataset.source_path}")
        click.echo(f"Legend: {dataset.legend_name}")
        click.echo(f"Name:   {dataset.dataset_name}")
    for expr_spec in expression_specs:
        click.echo(f"Expr:   {expr_spec.expression_text}")
        click.echo(f"Legend: {expr_spec.legend_name}")
        click.echo(f"Name:   {expr_spec.dataset_name}")
    click.echo(f"Output: {written}")

    if open_browser:
        webbrowser.open(written.as_uri())


def main() -> None:
    cli()
