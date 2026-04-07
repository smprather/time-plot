from __future__ import annotations

import os
import sys
from pathlib import Path
import webbrowser

import numpy as np
import rich_click as click

from time_plot.plotting import write_multi_html
from time_plot.vendor.ascii_histogram import DataSet, Histogram
from time_plot.plugin_system import discover_plugins_from_dirs
from time_plot.processing import (
    ExpressionDef,
    FileGroup,
    align_registry,
    combine_plot_data,
    evaluate_expressions,
    list_series_for_groups,
    load_file_groups,
)


def _series_rms(y: np.ndarray) -> float:
    finite = y[np.isfinite(y)]
    if finite.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(finite ** 2)))


def _rms_histogram(rms_values: list[float], units: str) -> str:
    finite = [v for v in rms_values if np.isfinite(v)]
    if not finite:
        return "(no finite RMS values to histogram)"
    bucket_size, num_buckets, middle_value = Histogram.auto_size(finite)
    ds = DataSet(finite, label="RMS", units=units)
    h = Histogram(num_buckets=num_buckets, bucket_size=bucket_size, middle_value=middle_value)
    h << ds
    return h.gen_histogram()


def _default_plugins_dir() -> Path:
    return Path(__file__).parent / "plugins"


def _default_example_path() -> Path:
    return Path(__file__).parent / "example_data" / "sine.csv"


def _build_file_groups(
    args: list[str],
) -> tuple[list[FileGroup], list[ExpressionDef]]:
    """Parse sys.argv-style args in order to build FileGroup and ExpressionDef lists.

    Processes -f, -F, -R, -e flags in the order they appear so that -F/-R binds
    to the preceding -f group.

    This is called with the raw remaining args after Click has consumed its own
    options, so only the per-group flags need to be handled here.
    """
    groups: list[FileGroup] = []
    expr_defs: list[ExpressionDef] = []

    # Pending files not yet assigned to a group
    pending_files: list[Path] = []

    def _flush_pending(glob_filter: str | None = None, regex_filter: str | None = None) -> None:
        if pending_files:
            groups.append(FileGroup(
                files=list(pending_files),
                glob_filter=glob_filter,
                regex_filter=regex_filter,
            ))
            pending_files.clear()

    i = 0
    while i < len(args):
        arg = args[i]

        if arg in ("-f", "--file"):
            i += 1
            if i >= len(args):
                raise click.ClickException("-f requires a file path argument")
            path = Path(args[i])
            if not path.exists():
                raise click.ClickException(f"Input file not found: {path}")
            pending_files.append(path)
            # consume additional non-flag args as more files (shell glob expansion)
            while i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                path = Path(args[i])
                if not path.exists():
                    raise click.ClickException(f"Input file not found: {path}")
                pending_files.append(path)

        elif arg.startswith("-f") and len(arg) > 2:
            # -f/path/to/file (no space)
            path = Path(arg[2:])
            if not path.exists():
                raise click.ClickException(f"Input file not found: {path}")
            pending_files.append(path)

        elif arg in ("-F", "--filter"):
            i += 1
            if i >= len(args):
                raise click.ClickException("-F requires a glob pattern argument")
            _flush_pending(glob_filter=args[i])

        elif arg.startswith("-F") and len(arg) > 2:
            _flush_pending(glob_filter=arg[2:])

        elif arg in ("-R", "--regex-filter"):
            i += 1
            if i >= len(args):
                raise click.ClickException("-R requires a regex argument")
            _flush_pending(regex_filter=args[i])

        elif arg.startswith("-R") and len(arg) > 2:
            _flush_pending(regex_filter=arg[2:])

        elif arg in ("-e", "--expr"):
            i += 1
            if i >= len(args):
                raise click.ClickException("-e requires a 'name=expr' argument")
            _parse_expr_arg(args[i], expr_defs)

        elif arg.startswith("-e") and len(arg) > 2:
            _parse_expr_arg(arg[2:], expr_defs)

        else:
            raise click.ClickException(
                f"Unexpected argument: {arg!r}. Use -f to specify source files."
            )

        i += 1

    # Flush any trailing files with no filter
    _flush_pending()

    return groups, expr_defs


def _parse_expr_arg(text: str, out: list[ExpressionDef]) -> None:
    eq = text.find("=")
    if eq == -1:
        raise click.ClickException(
            f"Expression must have the form 'name=expr', got: {text!r}"
        )
    name = text[:eq].strip()
    if not name.isidentifier():
        raise click.ClickException(
            f"Expression name must be a simple identifier, got: {name!r}"
        )
    expr_text = text[eq + 1:].strip()
    if not expr_text:
        raise click.ClickException(f"Empty expression body in: {text!r}")
    out.append(ExpressionDef(name=name, expr_text=expr_text))


@click.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
@click.argument("extra_args", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "-o", "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="HTML output path. Defaults to /tmp/$USER/time_plot.html.",
)
@click.option(
    "--add-plugins-dir",
    "extra_plugin_dirs",
    type=click.Path(path_type=Path, file_okay=False),
    multiple=True,
    help="Additional plugin directory (repeatable; last given has highest precedence).",
)
@click.option(
    "--parser-options",
    "parser_options_raw",
    type=str,
    default=None,
    help="Comma-separated key=value pairs passed to parser plugins (escape hatch).",
)
@click.option(
    "--open-browser/--no-open-browser",
    default=True,
    help="Open the output HTML in the default browser after writing (default: true).",
)
@click.option(
    "-l", "--list-series",
    "list_series",
    is_flag=True,
    default=False,
    help="List available series for each file (with -F/-R applied) and exit.",
)
@click.option(
    "-i", "--case-insensitive",
    "case_insensitive",
    is_flag=True,
    default=False,
    help="Apply -F/-R filters case-insensitively.",
)
@click.option(
    "--show-rms-histogram",
    "show_rms_histogram",
    is_flag=True,
    default=False,
    help="Print an ASCII histogram of per-series RMS values after loading.",
)
@click.option(
    "--list-plugins",
    "list_plugins",
    is_flag=True,
    default=False,
    help="List all discovered plugins with short descriptions and exit.",
)
@click.option(
    "--plugin-help",
    "plugin_help",
    type=str,
    default=None,
    metavar="PLUGIN",
    help="Show detailed help for a named plugin and exit.",
)
@click.option(
    "--rms-filter",
    "rms_filter",
    type=float,
    default=None,
    metavar="THRESHOLD",
    help="Exclude series whose RMS is below THRESHOLD (same units as the data).",
)
def cli(
    extra_args: tuple[str, ...],
    output_path: Path | None,
    extra_plugin_dirs: tuple[Path, ...],
    parser_options_raw: str | None,
    open_browser: bool,
    list_series: bool,
    case_insensitive: bool,
    show_rms_histogram: bool,
    rms_filter: float | None,
    list_plugins: bool,
    plugin_help: str | None,
) -> None:
    """Plot time-series data from files via pluggable parsers.

    \b
    Source and filter flags (order-sensitive):
      -f <path...>  Load one or more source files. Repeatable. Shell globs work:
                    -f *.ptiavg loads all matching files into one group.
      -F <glob>     Glob filter on series names; binds to preceding -f flags.
                    No glob chars → substring match (foo → *foo*).
      -R <regex>    Regex filter; same binding semantics as -F. ANDed with -F.
      -i            Apply -F/-R case-insensitively.

    \b
    Examples:
      time_plot -f signal.csv
      time_plot -f data.ptiavg -F 'rtr_0*' -l
      time_plot -f data.ptiavg -F 'rtr_0*' -e "total=sum(*|rtr_0*)"
      time_plot -f a.ptiavg -F 'mac*' -f b.ptiavg -F 'cts*' -e "diff=mac|inst-cts|inst"

    \b
    Expression syntax:
      name=<expr>   arithmetic: +  -  *  /
      ddt(x)        derivative (unit/s)
      abs(x)        absolute value
      rms(x)        RMS → scalar horizontal line
      average(x)    mean → scalar horizontal line
      sum(*|pat)    aggregate matching series → single trace

    \b
    Series references in expressions:
      foo           matches any series whose name contains 'foo'
      file|foo      matches file containing 'file' and series containing 'foo'
      *|foo*        explicit glob syntax

    Output defaults to /tmp/$USER/time_plot.html.
    """
    parser_options: dict[str, str] = {}
    if parser_options_raw:
        for pair in parser_options_raw.split(","):
            if "=" not in pair:
                raise click.ClickException(f"Invalid parser option (missing '='): {pair}")
            key, value = pair.split("=", 1)
            parser_options[key.strip()] = value.strip()

    # Plugin search order (highest precedence first):
    #   --add-plugins-dir flags (reversed so last given = first checked)
    #   TIME_PLOT_EXTRA_PLUGINS_PATH entries (colon-separated)
    #   built-in plugins dir (always last)
    env_dirs = [
        Path(p) for p in os.environ.get("TIME_PLOT_EXTRA_PLUGINS_PATH", "").split(":")
        if p
    ]
    plugin_dirs = [*reversed(extra_plugin_dirs), *env_dirs, _default_plugins_dir()]
    plugins = discover_plugins_from_dirs(plugin_dirs)
    if not plugins:
        raise click.ClickException("No plugins found in any plugin directory")

    # --list-plugins
    if list_plugins:
        name_width = max(len(p.plugin_name) for p in plugins)
        for p in plugins:
            desc = p.short_description or "(no description)"
            click.echo(f"  {p.plugin_name:<{name_width}}  {desc}")
        return

    # --plugin-help <name>
    if plugin_help is not None:
        match = next((p for p in plugins if p.plugin_name == plugin_help), None)
        if match is None:
            available = ", ".join(p.plugin_name for p in plugins)
            raise click.ClickException(
                f"Unknown plugin {plugin_help!r}. Available: {available}"
            )
        click.echo(match.long_description or match.short_description or "(no help available)")
        return

    # Parse the per-group flags from the unprocessed args
    args = list(extra_args)
    try:
        groups, expr_defs = _build_file_groups(args)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    # RMS options require enumerating series; treat unfiltered groups as -F '*'
    if show_rms_histogram or rms_filter is not None:
        groups = [
            FileGroup(files=g.files, glob_filter="*", regex_filter=g.regex_filter)
            if g.glob_filter is None and g.regex_filter is None
            else g
            for g in groups
        ]

    # --list-series: print filtered names and exit
    if list_series:
        if not groups:
            raise click.ClickException("--list-series requires at least one -f source file.")
        try:
            if rms_filter is not None:
                # Need data to compute RMS — load and align, then filter
                registry = load_file_groups(groups, plugins, parser_options=parser_options, case_insensitive=case_insensitive)
                aligned_files = align_registry(registry)
                rms_values = [_series_rms(t.y) for t in aligned_files.traces]
                # Group surviving series back by source file
                series_by_file: dict[Path, list[str]] = {}
                for t, rms in zip(aligned_files.traces, rms_values):
                    if rms >= rms_filter and t.source_path is not None:
                        series_by_file.setdefault(t.source_path, []).append(t.legend_name)
            else:
                series_by_file = list_series_for_groups(groups, plugins, parser_options=parser_options, case_insensitive=case_insensitive)
        except (LookupError, ValueError, RuntimeError) as exc:
            raise click.ClickException(str(exc)) from exc
        for file_path, names in series_by_file.items():
            click.echo(f"{file_path}  ({len(names)} series)")
            for name in names:
                click.echo(f"  {name}")
        return

    # If no files were specified, use the built-in example
    if not groups:
        if expr_defs:
            raise click.ClickException("Expressions require at least one -f source file.")
        example = _default_example_path()
        groups = [FileGroup(files=[example])]

    try:
        registry = load_file_groups(groups, plugins, parser_options=parser_options, case_insensitive=case_insensitive)
        aligned_files = align_registry(registry)
    except (LookupError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    # RMS filter (applied to file traces before expressions)
    if show_rms_histogram or rms_filter is not None:
        rms_values = [_series_rms(t.y) for t in aligned_files.traces]
        if show_rms_histogram:
            click.echo(_rms_histogram(rms_values, aligned_files.traces[0].y_unit if aligned_files.traces else ""))
            return
        if rms_filter is not None:
            pairs = [(t, r) for t, r in zip(aligned_files.traces, rms_values) if r >= rms_filter]
            click.echo(f"RMS filter {rms_filter}: kept {len(pairs)}/{len(aligned_files.traces)} series")
            aligned_files = aligned_files.__class__(
                x_seconds=aligned_files.x_seconds,
                traces=[t for t, _ in pairs],
                x_timestep_seconds=aligned_files.x_timestep_seconds,
                x_display_prefix=aligned_files.x_display_prefix,
            )

    try:
        expr_traces = evaluate_expressions(aligned_files, expr_defs, registry)
        aligned = combine_plot_data(aligned_files, expr_traces)
    except (LookupError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Sort all traces (file + expressions) by RMS descending
    all_rms = [_series_rms(t.y) for t in aligned.traces]
    sorted_traces = [t for t, _ in sorted(zip(aligned.traces, all_rms), key=lambda p: p[1], reverse=True)]
    aligned = aligned.__class__(
        x_seconds=aligned.x_seconds,
        traces=sorted_traces,
        x_timestep_seconds=aligned.x_timestep_seconds,
        x_display_prefix=aligned.x_display_prefix,
    )

    # Determine output path
    if output_path is None:
        output_path = Path("/tmp") / os.environ.get("USER", "time_plot") / "time_plot.html"

    # Title
    title_parts = [t.legend_name for t in aligned.traces]
    if len(title_parts) == 1:
        title = aligned.traces[0].source_name
    else:
        title = ", ".join(title_parts[:4])
        if len(title_parts) > 4:
            title += f" (+{len(title_parts) - 4} more)"

    written = write_multi_html(aligned, output_path, title=title)

    for t in aligned_files.traces:
        click.echo(f"Series: {t.registry_key}")
    for e in expr_defs:
        click.echo(f"Expr:   {e.name}={e.expr_text}")
    click.echo(f"Output: {written}")

    if open_browser:
        webbrowser.open(written.as_uri())


def main() -> None:
    cli()
