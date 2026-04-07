from __future__ import annotations

import html
import json
from importlib.resources import files
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData
from time_plot.processing import AlignedPlotData, AlignedTrace
from time_plot.units import scale_for_display

# 10-color Tableau palette
_PALETTE = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
]


def _uplot_inline_assets() -> tuple[str, str, str]:
    static = files("uplot.static")
    css = (static / "uPlot.min.css").read_text(encoding="utf-8")
    js = (static / "uPlot.iife.js").read_text(encoding="utf-8")
    mousewheel = (static / "uPlot.mousewheel.js").read_text(encoding="utf-8")
    return css, js, mousewheel


def write_html(series: SeriesData, output_path: Path) -> Path:
    trace = AlignedTrace(
        registry_key="f1",
        legend_name=series.y_label,
        source_name=series.source_name,
        source_path=None,
        y_label=series.y_label,
        y_unit=series.y_unit,
        y_unit_label=series.y_unit_label,
        y=series.y,
        y_display_prefix=series.y_display_prefix,
    )
    plot_data = AlignedPlotData(
        x_seconds=series.x,
        traces=[trace],
        x_display_prefix=series.x_display_prefix,
    )
    return write_multi_html(plot_data, output_path, title=series.source_name)


def write_multi_html(
    plot_data: AlignedPlotData,
    output_path: Path,
    *,
    title: str = "Time Plot",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x_scaled = scale_for_display(
        plot_data.x_seconds,
        base_unit="s",
        forced_prefix=plot_data.x_display_prefix,
    )
    x_axis_label = f"Time ({x_scaled.display_unit})"

    legend_names = _dedupe_labels([trace.legend_name for trace in plot_data.traces])
    y_unit_order = _ordered_y_units(plot_data.traces)
    if len(y_unit_order) > 2:
        msg = "uPlot output supports at most two y-axis units."
        raise ValueError(msg)

    y_unit_scalers: dict[str, tuple[float, str]] = {}
    y_unit_labels: dict[str, str] = {}
    for unit in y_unit_order:
        unit_traces = [trace for trace in plot_data.traces if trace.y_unit == unit]
        values = np.concatenate([trace.y[np.isfinite(trace.y)] for trace in unit_traces]) if unit_traces else np.array([], dtype=np.float64)
        forced_prefixes = {trace.y_display_prefix for trace in unit_traces if trace.y_display_prefix is not None}
        forced_prefix = next(iter(forced_prefixes)) if len(forced_prefixes) == 1 else None
        scaled = scale_for_display(values if values.size else np.asarray([0.0]), base_unit=unit, forced_prefix=forced_prefix)
        y_unit_scalers[unit] = (scaled.factor, scaled.display_unit)
        y_unit_labels[unit] = unit_traces[0].y_unit_label if unit_traces else unit

    # Build columnar data: [[x_vals], [y1_vals], [y2_vals], ...]
    x_col: list[float | None] = [float(v) for v in x_scaled.scaled_values.tolist()]
    columns: list[list[float | None]] = [x_col]
    for trace in plot_data.traces:
        factor, _ = y_unit_scalers[trace.y_unit]
        col: list[float | None] = []
        for y_value in trace.y:
            if np.isfinite(y_value):
                col.append(float(y_value / factor))
            else:
                col.append(None)
        columns.append(col)

    # Build uPlot series config: index 0 = x placeholder
    series_configs: list[dict] = [{"label": "Time"}]
    first_unit = y_unit_order[0]
    secondary_unit = y_unit_order[1] if len(y_unit_order) > 1 else None

    for i, trace in enumerate(plot_data.traces):
        cfg: dict = {
            "label": legend_names[i],
            "stroke": _PALETTE[i % len(_PALETTE)],
            "width": 2,
            "alpha": 0.3,
        }
        if secondary_unit and trace.y_unit == secondary_unit:
            cfg["scale"] = "y2"
        series_configs.append(cfg)

    # Build axes config
    _, y_display_1 = y_unit_scalers[first_unit]
    y_axis_label_1 = f"{y_unit_labels[first_unit]} ({y_display_1})"
    axes_configs: list[dict] = [
        {"label": x_axis_label},
        {"label": y_axis_label_1},
    ]
    if secondary_unit:
        _, y_display_2 = y_unit_scalers[secondary_unit]
        y_axis_label_2 = f"{y_unit_labels[secondary_unit]} ({y_display_2})"
        axes_configs.append({"label": y_axis_label_2, "side": 1, "scale": "y2"})

    single_y_unit = len(y_unit_order) == 1
    if single_y_unit:
        _, header_display_unit = y_unit_scalers[first_unit]
        table_headers = {
            "peak_abs": f"Peak |y| ({header_display_unit})",
            "average": f"Average ({header_display_unit})",
            "rms": f"RMS ({header_display_unit})",
        }
    else:
        table_headers = {
            "peak_abs": "Peak |y|",
            "average": "Average",
            "rms": "RMS",
        }

    summary_rows: list[dict[str, str]] = []
    for i, trace in enumerate(plot_data.traces):
        finite = trace.y[np.isfinite(trace.y)]
        if finite.size:
            peak_abs = float(np.max(np.abs(finite)))
            average = float(np.mean(finite))
            rms_val = float(np.sqrt(np.mean(finite**2)))
        else:
            peak_abs = average = rms_val = float("nan")
        factor, display_unit = y_unit_scalers[trace.y_unit]
        if single_y_unit:
            fmt = lambda v, f=factor: f"{v / f:.4g}"
        else:
            fmt = lambda v, f=factor, u=display_unit: f"{v / f:.4g} {u}"
        summary_rows.append({
            "label": legend_names[i],
            "peak_abs": fmt(peak_abs),
            "average": fmt(average),
            "rms": fmt(rms_val),
        })

    source_rows: list[dict[str, str]] = []
    for i, trace in enumerate(plot_data.traces):
        source = str(trace.source_path) if trace.source_path is not None else trace.source_name
        source_rows.append({"label": legend_names[i], "source": source})

    html_text = _render_multi_html(
        title=title,
        columns=columns,
        series_configs=series_configs,
        axes_configs=axes_configs,
        summary_rows=summary_rows,
        table_headers=table_headers,
        source_rows=source_rows,
    )
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def _render_multi_html(
    *,
    title: str,
    columns: list[list[float | None]],
    series_configs: list[dict],
    axes_configs: list[dict],
    summary_rows: list[dict[str, str]],
    table_headers: dict[str, str],
    source_rows: list[dict[str, str]],
) -> str:
    columns_json = json.dumps(columns)
    series_json = json.dumps(series_configs)
    axes_json = json.dumps(axes_configs)
    title_json = json.dumps(title)
    safe_title = html.escape(title)

    table_rows = ""
    for row in summary_rows:
        table_rows += (
            f"        <tr>"
            f"<td>{html.escape(row['label'])}</td>"
            f"<td>{html.escape(row['peak_abs'])}</td>"
            f"<td>{html.escape(row['average'])}</td>"
            f"<td>{html.escape(row['rms'])}</td>"
            f"</tr>\n"
        )

    source_table_rows = ""
    for row in source_rows:
        source_table_rows += (
            f"        <tr>"
            f"<td>{html.escape(row['label'])}</td>"
            f"<td>{html.escape(row['source'])}</td>"
            f"</tr>\n"
        )

    uplot_css, uplot_js, mousewheel_js = _uplot_inline_assets()
    # Escape </script> in inlined JS to avoid breaking the HTML parser
    uplot_js_safe = uplot_js.replace("</script>", "<\\/script>")
    mousewheel_js_safe = mousewheel_js.replace("</script>", "<\\/script>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
{uplot_css}
  </style>
  <style>
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: #f7f7f2;
      color: #101010;
    }}
    .wrap {{
      max-width: 1100px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .card {{
      background: white;
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 12px;
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.06);
    }}
    #plot {{
      width: 100%;
      min-height: 560px;
      position: relative;
    }}
    #focused-label {{
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(0,0,0,0.65);
      color: #fff;
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 4px;
      pointer-events: none;
      white-space: nowrap;
      display: none;
    }}
    .meta {{
      margin: 0 0 12px 0;
      color: #444;
      font-size: 14px;
    }}
    .u-legend {{
      display: flex;
      flex-direction: column;
      text-align: left;
    }}
    .summary {{
      margin: 16px 0 0 0;
      border-collapse: collapse;
      width: 100%;
      font-size: 14px;
    }}
    .summary th, .summary td {{
      border: 1px solid #ddd;
      padding: 6px 12px;
      text-align: right;
    }}
    .summary th {{
      background: #f7f7f2;
      font-weight: 600;
    }}
    .summary td:first-child, .summary th:first-child {{
      text-align: left;
    }}
  </style>
</head>
<body>
    <div class="wrap">
      <div class="card">
      <p class="meta">Left-mouse double-click to zoom full</p>
      <div id="plot" aria-label="Time series plot">
        <div id="focused-label"></div>
      </div>
      <table class="summary">
        <thead>
          <tr><th>Label</th><th>{html.escape(table_headers["peak_abs"])}</th><th>{html.escape(table_headers["average"])}</th><th>{html.escape(table_headers["rms"])}</th></tr>
        </thead>
        <tbody>
{table_rows}        </tbody>
      </table>
      <table class="summary">
        <thead>
          <tr><th>Label</th><th>Input File</th></tr>
        </thead>
        <tbody>
{source_table_rows}        </tbody>
      </table>
    </div>
  </div>
  <script>
{uplot_js_safe}
  </script>
  <script>
{mousewheel_js_safe}
  </script>
  <script>
    (function() {{
      const data = {columns_json};
      const title = {title_json};

      const plotEl = document.getElementById("plot");
      const rect = plotEl.getBoundingClientRect();

      const opts = {{
        width: Math.floor(rect.width) || 900,
        height: 560,
        scales: {{
          x: {{ time: false }}
        }},
        series: {series_json},
        axes: {axes_json},
        cursor: {{
          drag: {{
            x: true,
            y: true,
            uni: 50,
            setScale: true
          }},
          focus: {{
            prox: 30
          }}
        }},
        plugins: [
          wheelZoomPlugin({{ factor: 0.75 }})
        ],
        hooks: {{
          setSeries: [function(u, i, opts) {{
            if (!opts.focus) return;
            const el = document.getElementById("focused-label");
            if (i == null) {{
              el.style.display = "none";
            }} else {{
              el.textContent = u.series[i].label;
              el.style.display = "block";
            }}
          }}]
        }}
      }};

      const uplot = new uPlot(opts, data, plotEl);

      window.addEventListener("resize", function() {{
        const w = plotEl.parentElement.clientWidth - 24;
        if (w > 0) uplot.setSize({{ width: w, height: 560 }});
      }});
    }})();
  </script>
</body>
</html>
"""


def html_escape_json_string(value: str) -> str:
    return json.dumps(value)


def _ordered_y_units(traces: list[AlignedTrace]) -> list[str]:
    seen: set[str] = set()
    units: list[str] = []
    for trace in traces:
        if trace.y_unit in seen:
            continue
        seen.add(trace.y_unit)
        units.append(trace.y_unit)
    return units


def _dedupe_labels(labels: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    output: list[str] = []
    for label in labels:
        count = counts.get(label, 0) + 1
        counts[label] = count
        output.append(label if count == 1 else f"{label} [{count}]")
    return output
