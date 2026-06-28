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
_LOGIC_NORMAL_COLOR = "#2ca02c"
_LOGIC_Z_COLOR = "#f28e2b"
_LOGIC_X_COLOR = "#d62728"


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
        sample_mode=series.sample_mode,
        logic_states=series.logic_states,
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
    logic_lane_by_trace = _logic_lane_by_trace(plot_data.traces)
    logic_labels_by_scale: dict[str, list[str]] = {}

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

    first_unit = y_unit_order[0]
    secondary_unit = y_unit_order[1] if len(y_unit_order) > 1 else None
    unit_to_scale = {
        first_unit: "y",
        **({secondary_unit: "y2"} if secondary_unit is not None else {}),
    }

    # Build columnar data: [[x_vals], [y1_vals], [y2_vals], ...] and matching
    # uPlot series config. Logic traces expand to normal/Z/X overlay series.
    x_col: list[float | None] = [float(v) for v in x_scaled.scaled_values.tolist()]
    columns: list[list[float | None]] = [x_col]
    series_configs: list[dict] = [{"label": "Time"}]
    render_sample_modes: list[str] = []
    for i, trace in enumerate(plot_data.traces):
        scale_name = "y2" if secondary_unit and trace.y_unit == secondary_unit else None
        lane = logic_lane_by_trace.get(i)
        if lane is not None:
            for logic_style in ("normal", "z", "x_low", "x_high"):
                columns.append(_logic_style_column(trace, lane, logic_style))
                series_configs.append(_logic_series_config(legend_names[i], logic_style, scale_name))
                render_sample_modes.append("logic")
            continue

        factor, _ = y_unit_scalers[trace.y_unit]
        col: list[float | None] = []
        for y_value in trace.y:
            col.append(float(y_value / factor) if np.isfinite(y_value) else None)
        columns.append(col)

        cfg: dict = {
            "label": legend_names[i],
            "stroke": _PALETTE[i % len(_PALETTE)],
            "width": 2,
            "alpha": 0.3,
        }
        if scale_name is not None:
            cfg["scale"] = scale_name
        series_configs.append(cfg)
        render_sample_modes.append(trace.sample_mode)

    # Build axes config
    _, y_display_1 = y_unit_scalers[first_unit]
    y_axis_label_1 = _axis_label(y_unit_labels[first_unit], y_display_1, first_unit)
    axes_configs: list[dict] = [
        {"label": x_axis_label},
        {"label": y_axis_label_1},
    ]
    if secondary_unit:
        _, y_display_2 = y_unit_scalers[secondary_unit]
        y_axis_label_2 = _axis_label(y_unit_labels[secondary_unit], y_display_2, secondary_unit)
        axes_configs.append({"label": y_axis_label_2, "side": 1, "scale": "y2"})

    for unit, scale in unit_to_scale.items():
        if unit != "logic":
            continue
        lane_labels = _logic_lane_labels(plot_data.traces, legend_names, logic_lane_by_trace)
        if lane_labels:
            logic_labels_by_scale[scale] = lane_labels

    for axis in axes_configs[1:]:
        scale = axis.get("scale", "y")
        if scale in logic_labels_by_scale:
            axis["logicLabels"] = logic_labels_by_scale[scale]

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

    show_summary = not logic_lane_by_trace
    summary_rows: list[dict[str, str]] = []
    if show_summary:
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
                def fmt(v: float, f: float = factor) -> str:
                    return f"{v / f:.4g}"
            else:
                def fmt(v: float, f: float = factor, u: str = display_unit) -> str:
                    return f"{v / f:.4g} {u}"
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
        sample_modes=render_sample_modes,
        scale_configs=_scale_configs(logic_labels_by_scale),
        show_summary=show_summary,
        has_logic=bool(logic_lane_by_trace),
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
    sample_modes: list[str],
    scale_configs: dict[str, dict[str, object]],
    show_summary: bool,
    has_logic: bool,
) -> str:
    columns_json = json.dumps(columns)
    series_json = json.dumps(series_configs)
    axes_json = json.dumps(axes_configs)
    sample_modes_json = json.dumps(sample_modes)
    scale_configs_json = json.dumps(scale_configs)
    cursor_focus_prox = -1 if has_logic else 30
    title_json = json.dumps(title)
    safe_title = html.escape(title)

    summary_table = ""
    if show_summary:
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
        summary_table = (
            f"      <table class=\"summary\">\n"
            f"        <thead>\n"
            f"          <tr><th>Label</th><th>{html.escape(table_headers['peak_abs'])}</th>"
            f"<th>{html.escape(table_headers['average'])}</th>"
            f"<th>{html.escape(table_headers['rms'])}</th></tr>\n"
            f"        </thead>\n"
            f"        <tbody>\n"
            f"{table_rows}        </tbody>\n"
            f"      </table>\n"
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
{summary_table}
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
      const sampleModes = {sample_modes_json};
      const scales = {scale_configs_json};
      const axes = {axes_json};

      const plotEl = document.getElementById("plot");
      const rect = plotEl.getBoundingClientRect();

      for (const axis of axes) {{
        const labels = axis.logicLabels;
        if (labels) {{
          delete axis.logicLabels;
          axis.splits = function() {{
            return labels.map((_, idx) => idx + 0.5);
          }};
          axis.values = function(u, vals) {{
            return vals.map((value) => labels[Math.round(value - 0.5)] || "");
          }};
        }}
      }}

      const series = {series_json};
      for (let i = 1; i < series.length; i++) {{
        if (sampleModes[i - 1] === "logic") {{
          series[i].paths = logicIntervalPaths();
        }} else if (sampleModes[i - 1] === "step") {{
          series[i].paths = uPlot.paths.stepped({{ align: 1 }});
        }}
      }}
      const logicGroups = buildLogicGroups(series);
      for (const group of logicGroups) {{
        series[group.main].value = function(u, value, seriesIdx, idx) {{
          return logicValueForGroupAtIndex(u, group, idx);
        }};
      }}

      const opts = {{
        width: Math.floor(rect.width) || 900,
        height: 560,
        scales: scales,
        series: series,
        axes: axes,
        cursor: {{
          dataIdx: function(u, seriesIdx, cursorIdx, xValue) {{
            if (series[seriesIdx] && series[seriesIdx].logicGroup) {{
              return logicIntervalIndexForX(u.data[0], xValue, cursorIdx);
            }}
            return cursorIdx;
          }},
          drag: {{
            x: true,
            y: true,
            uni: 50,
            setScale: true
          }},
          focus: {{
            prox: {cursor_focus_prox}
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
      const legendRows = Array.from(plotEl.querySelectorAll(".u-legend .u-series"));
      for (let i = 1; i < series.length; i++) {{
        if (series[i].legendShow === false && legendRows[i]) {{
          legendRows[i].style.display = "none";
        }}
      }}
      installLogicLegendGroups(uplot, logicGroups, legendRows);

      window.addEventListener("resize", function() {{
        const w = plotEl.parentElement.clientWidth - 24;
        if (w > 0) uplot.setSize({{ width: w, height: 560 }});
      }});

      function logicIntervalPaths() {{
        return function(u, seriesIdx, idx0, idx1) {{
          const stroke = new Path2D();
          const dataX = u.data[0];
          const dataY = u.data[seriesIdx];
          const series = u.series[seriesIdx];
          const xScale = u.series[0].scale || "x";
          const yScale = series.scale || "y";
          const start = Math.max(0, idx0 - 1);
          const end = Math.min(idx1, dataX.length - 2);

          for (let i = start; i <= end; i++) {{
            const y = dataY[i];
            if (y == null) continue;

            const x0 = u.valToPos(dataX[i], xScale, true);
            const x1 = u.valToPos(dataX[i + 1], xScale, true);
            const y0 = u.valToPos(y, yScale, true);
            stroke.moveTo(x0, y0);
            stroke.lineTo(x1, y0);

            const nextY = dataY[i + 1];
            if (nextY != null && nextY !== y) {{
              stroke.lineTo(x1, u.valToPos(nextY, yScale, true));
            }}
          }}

          return {{ stroke: stroke, fill: null, clip: null }};
        }};
      }}

      function buildLogicGroups(series) {{
        const byName = new Map();
        for (let i = 1; i < series.length; i++) {{
          const groupName = series[i].logicGroup;
          if (!groupName) continue;
          let group = byName.get(groupName);
          if (!group) {{
            group = {{ name: groupName, indexes: [], roles: {{}}, main: null }};
            byName.set(groupName, group);
          }}
          group.indexes.push(i);
          group.roles[series[i].logicRole] = i;
          if (series[i].logicRole === "normal") {{
            group.main = i;
          }}
        }}
        return Array.from(byName.values()).filter((group) => group.main != null);
      }}

      function installLogicLegendGroups(u, groups, legendRows) {{
        for (const group of groups) {{
          const row = legendRows[group.main];
          if (!row) continue;
          row.addEventListener("click", function(event) {{
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            const show = !u.series[group.main].show;
            u.batch(function() {{
              for (const seriesIdx of group.indexes) {{
                u.setSeries(seriesIdx, {{show: show}}, true);
              }}
            }});
          }}, true);
        }}
      }}

      function logicValueForGroupAtIndex(u, group, idx) {{
        idx = Math.max(0, Math.min(u.data[0].length - 1, idx == null ? 0 : idx));
        const zIdx = group.roles.z;
        if (zIdx != null && u.data[zIdx][idx] != null) return "Z";

        const xIdx = group.roles.x_low;
        if (xIdx != null && u.data[xIdx][idx] != null) return "X";

        const normalIdx = group.roles.normal;
        const y = normalIdx == null ? null : u.data[normalIdx][idx];
        if (y == null) return "--";
        return y - Math.floor(y) >= 0.5 ? "1" : "0";
      }}

      function logicIntervalIndexForX(dataX, xValue, fallbackIdx) {{
        if (dataX.length === 0) return 0;

        if (!Number.isFinite(xValue)) {{
          const idx = fallbackIdx == null ? 0 : fallbackIdx;
          return Math.max(0, Math.min(dataX.length - 1, idx));
        }}

        let lo = 0;
        let hi = dataX.length - 1;
        while (lo < hi) {{
          const mid = Math.ceil((lo + hi) / 2);
          if (dataX[mid] <= xValue) {{
            lo = mid;
          }} else {{
            hi = mid - 1;
          }}
        }}
        return lo;
      }}
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


def _axis_label(unit_label: str, display_unit: str, unit: str) -> str:
    if unit == "logic":
        return ""
    return f"{unit_label} ({display_unit})"


def _is_logic_trace(trace: AlignedTrace) -> bool:
    return trace.y_unit == "logic" and trace.sample_mode == "step"


def _logic_lane_by_trace(traces: list[AlignedTrace]) -> dict[int, int]:
    logic_indices = [idx for idx, trace in enumerate(traces) if _is_logic_trace(trace)]
    lane_count = len(logic_indices)
    return {trace_idx: lane_count - order - 1 for order, trace_idx in enumerate(logic_indices)}


def _logic_series_config(label: str, logic_style: str, scale_name: str | None) -> dict:
    cfg: dict = {
        "label": label if logic_style == "normal" else f"{label} {logic_style.replace('_', ' ')}",
        "stroke": _logic_style_color(logic_style),
        "width": 2,
        "alpha": 1.0,
        "points": {"show": False},
        "logicGroup": label,
        "logicRole": logic_style,
        "legendShow": logic_style == "normal",
    }
    if scale_name is not None:
        cfg["scale"] = scale_name
    return cfg


def _logic_style_color(logic_style: str) -> str:
    if logic_style == "z":
        return _LOGIC_Z_COLOR
    if logic_style in {"x_low", "x_high"}:
        return _LOGIC_X_COLOR
    return _LOGIC_NORMAL_COLOR


def _logic_style_column(trace: AlignedTrace, lane: int, logic_style: str) -> list[float | None]:
    states = _logic_states(trace)
    col: list[float | None] = []
    for state in states:
        if _logic_style_matches(logic_style, state):
            col.append(_logic_style_value(logic_style, state, lane))
        else:
            col.append(None)
    return col


def _logic_states(trace: AlignedTrace) -> list[str]:
    if trace.logic_states is not None:
        return [str(state).lower() for state in trace.logic_states.tolist()]
    states: list[str] = []
    for value in trace.y:
        if not np.isfinite(value):
            states.append("")
        elif value >= 0.5:
            states.append("1")
        else:
            states.append("0")
    return states


def _logic_style_matches(logic_style: str, state: str) -> bool:
    if logic_style == "normal":
        return state in {"0", "1"}
    if logic_style == "z":
        return state == "z"
    if logic_style in {"x_low", "x_high"}:
        return state == "x"
    return False


def _logic_style_value(logic_style: str, state: str, lane: int) -> float:
    if logic_style == "z":
        return lane + 0.5
    if logic_style == "x_low":
        return lane + 0.15
    if logic_style == "x_high":
        return lane + 0.85
    return lane + (0.85 if state == "1" else 0.15)


def _logic_lane_labels(
    traces: list[AlignedTrace],
    legend_names: list[str],
    lane_by_trace: dict[int, int],
) -> list[str]:
    if not lane_by_trace:
        return []
    labels = [""] * len(lane_by_trace)
    for trace_idx, lane in lane_by_trace.items():
        labels[lane] = legend_names[trace_idx]
    return labels


def _scale_configs(logic_labels_by_scale: dict[str, list[str]]) -> dict[str, dict[str, object]]:
    scales: dict[str, dict[str, object]] = {"x": {"time": False}}
    for scale, labels in logic_labels_by_scale.items():
        scales[scale] = {"range": [0, max(1, len(labels))]}
    return scales


def _dedupe_labels(labels: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    output: list[str] = []
    for label in labels:
        count = counts.get(label, 0) + 1
        counts[label] = count
        output.append(label if count == 1 else f"{label} [{count}]")
    return output
