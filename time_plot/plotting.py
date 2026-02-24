from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData
from time_plot.processing import AlignedPlotData, AlignedTrace
from time_plot.units import scale_for_display


DYGRAPHS_CDN_JS = "https://cdn.jsdelivr.net/npm/dygraphs@2.2.1/dist/dygraph.min.js"
DYGRAPHS_CDN_CSS = "https://cdn.jsdelivr.net/npm/dygraphs@2.2.1/dist/dygraph.min.css"
DYGRAPHS_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor" / "dygraphs"


def write_dygraphs_html(series: SeriesData, output_path: Path) -> Path:
    trace = AlignedTrace(
        dataset_name="f1",
        legend_name=series.y_label,
        source_name=series.source_name,
        y_label=series.y_label,
        y_unit=series.y_unit,
        y=series.y,
        y_display_prefix=series.y_display_prefix,
    )
    plot_data = AlignedPlotData(
        x_seconds=series.x,
        traces=[trace],
        x_display_prefix=series.x_display_prefix,
    )
    return write_multi_dygraphs_html(plot_data, output_path, title=series.source_name)


def write_multi_dygraphs_html(
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
    y_group_order = _ordered_y_groups(plot_data.traces)
    if len(y_group_order) > 2:
        msg = "Dygraphs output supports at most two y-axis types."
        raise ValueError(msg)

    y_group_scalers: dict[tuple[str, str], tuple[float, str]] = {}
    y_axis_labels: dict[tuple[str, str], str] = {}
    for group_key in y_group_order:
        traces = [trace for trace in plot_data.traces if (trace.y_label, trace.y_unit) == group_key]
        values = np.concatenate([trace.y[np.isfinite(trace.y)] for trace in traces]) if traces else np.array([], dtype=np.float64)
        forced_prefixes = {trace.y_display_prefix for trace in traces if trace.y_display_prefix is not None}
        forced_prefix = next(iter(forced_prefixes)) if len(forced_prefixes) == 1 else None
        scaled = scale_for_display(values if values.size else np.asarray([0.0]), base_unit=group_key[1], forced_prefix=forced_prefix)
        y_group_scalers[group_key] = (scaled.factor, scaled.display_unit)
        y_axis_labels[group_key] = f"{group_key[0]} ({scaled.display_unit})"

    rows: list[list[float | None]] = []
    for idx, x_value in enumerate(x_scaled.scaled_values.tolist()):
        row: list[float | None] = [float(x_value)]
        for trace in plot_data.traces:
            factor, _ = y_group_scalers[(trace.y_label, trace.y_unit)]
            y_value = trace.y[idx]
            if np.isfinite(y_value):
                row.append(float(y_value / factor))
            else:
                row.append(None)
        rows.append(row)

    dy_title = title
    first_group = y_group_order[0]
    y_label_1 = y_axis_labels[first_group]
    y_label_2 = y_axis_labels[y_group_order[1]] if len(y_group_order) > 1 else None

    series_axis_map: dict[str, dict[str, str]] = {}
    if len(y_group_order) > 1:
        secondary_group = y_group_order[1]
        for legend_name, trace in zip(legend_names, plot_data.traces, strict=False):
            if (trace.y_label, trace.y_unit) == secondary_group:
                series_axis_map[legend_name] = {"axis": "y2"}

    html_text = _render_multi_html(
        title=dy_title,
        source_name=dy_title,
        rows=rows,
        legend_names=legend_names,
        x_axis_label=x_axis_label,
        y_axis_label=y_label_1,
        y2_axis_label=y_label_2,
        series_axis_map=series_axis_map,
    )
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def _render_multi_html(
    *,
    title: str,
    source_name: str,
    rows: list[list[float | None]],
    legend_names: list[str],
    x_axis_label: str,
    y_axis_label: str,
    y2_axis_label: str | None,
    series_axis_map: dict[str, dict[str, str]],
) -> str:
    rows_json = json.dumps(rows)
    labels_json = json.dumps(["Time", *legend_names])
    title_json = json.dumps(title)
    xlabel_json = json.dumps(x_axis_label)
    ylabel_json = json.dumps(y_axis_label)
    y2label_json = json.dumps(y2_axis_label) if y2_axis_label is not None else "null"
    series_axis_map_json = json.dumps(series_axis_map)
    safe_title = html.escape(title)
    safe_source_name = html.escape(source_name)
    dygraphs_css_tag, dygraphs_js_tag = _dygraphs_asset_tags()

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  {dygraphs_css_tag}
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
      height: 560px;
    }}
    .meta {{
      margin: 0 0 12px 0;
      color: #444;
      font-size: 14px;
    }}
  </style>
</head>
<body>
    <div class="wrap">
      <div class="card">
      <p class="meta">Source: {safe_source_name}</p>
      <div id="plot" aria-label="Time series plot"></div>
    </div>
  </div>
  {dygraphs_js_tag}
  <script>
    const data = {rows_json};
    const labels = {labels_json};
    const title = {title_json};
    const xlabel = {xlabel_json};
    const ylabel = {ylabel_json};
    const y2label = {y2label_json};
    const seriesAxisMap = {series_axis_map_json};

    function renderFallbackSvg(container, rows) {{
      if (!rows.length) {{
        container.textContent = "No data to plot.";
        return;
      }}

      const width = container.clientWidth || 900;
      const height = container.clientHeight || 560;
      const m = {{ top: 24, right: 18, bottom: 42, left: 56 }};
      const plotW = Math.max(1, width - m.left - m.right);
      const plotH = Math.max(1, height - m.top - m.bottom);
      const xs = rows.map(r => r[0]);
      const ys = rows.map(r => r[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      let minY = Math.min(...ys);
      let maxY = Math.max(...ys);
      if (minY === maxY) {{
        minY -= 1;
        maxY += 1;
      }}

      const sx = (x) => m.left + ((x - minX) / (maxX - minX || 1)) * plotW;
      const sy = (y) => m.top + plotH - ((y - minY) / (maxY - minY || 1)) * plotH;
      const pathD = rows.map((r, i) => `${{i ? "L" : "M"}} ${{sx(r[0]).toFixed(2)}} ${{sy(r[1]).toFixed(2)}}`).join(" ");

      const zeroY = (minY <= 0 && 0 <= maxY) ? sy(0) : null;
      container.innerHTML = `
        <svg viewBox="0 0 ${{width}} ${{height}}" width="100%" height="100%" role="img" aria-label="${{title}}">
          <rect x="0" y="0" width="${{width}}" height="${{height}}" fill="#fff"/>
          <rect x="${{m.left}}" y="${{m.top}}" width="${{plotW}}" height="${{plotH}}" fill="#fff" stroke="#d0d0d0"/>
          ${{zeroY === null ? "" : `<line x1="${{m.left}}" y1="${{zeroY}}" x2="${{m.left + plotW}}" y2="${{zeroY}}" stroke="#ececec" />`}}
          <line x1="${{m.left}}" y1="${{m.top + plotH}}" x2="${{m.left + plotW}}" y2="${{m.top + plotH}}" stroke="#222"/>
          <line x1="${{m.left}}" y1="${{m.top}}" x2="${{m.left}}" y2="${{m.top + plotH}}" stroke="#222"/>
          <path d="${{pathD}}" fill="none" stroke="#1167b1" stroke-width="1.5"/>
          <text x="${{m.left + plotW / 2}}" y="${{height - 10}}" text-anchor="middle" font-size="12" fill="#333">${{xlabel}}</text>
          <text x="14" y="${{m.top + plotH / 2}}" text-anchor="middle" font-size="12" fill="#333"
                transform="rotate(-90 14 ${{m.top + plotH / 2}})">${{ylabel}}</text>
          <text x="${{m.left}}" y="${{m.top - 6}}" font-size="11" fill="#555">${{labels[1]}} vs ${{labels[0]}} (offline fallback)</text>
          <text x="${{m.left}}" y="${{m.top + plotH + 16}}" font-size="10" fill="#555">${{minX.toFixed(3)}}</text>
          <text x="${{m.left + plotW}}" y="${{m.top + plotH + 16}}" text-anchor="end" font-size="10" fill="#555">${{maxX.toFixed(3)}}</text>
          <text x="${{m.left - 6}}" y="${{m.top + 4}}" text-anchor="end" font-size="10" fill="#555">${{maxY.toFixed(3)}}</text>
          <text x="${{m.left - 6}}" y="${{m.top + plotH}}" text-anchor="end" dominant-baseline="ideographic" font-size="10" fill="#555">${{minY.toFixed(3)}}</text>
        </svg>
      `;
    }}

    const plotEl = document.getElementById("plot");
    if (window.Dygraph) {{
      const options = {{
        labels: labels,
        title: title,
        xlabel: xlabel,
        ylabel: ylabel,
        drawPoints: false,
        strokeWidth: 1.5,
        legend: "follow",
        animatedZooms: true
      }};
      if (y2label) options.y2label = y2label;
      if (Object.keys(seriesAxisMap).length) options.series = seriesAxisMap;
      new Dygraph(plotEl, data, options);
    }} else {{
      renderFallbackSvg(plotEl, data);
    }}
  </script>
</body>
</html>
"""


def _dygraphs_asset_tags() -> tuple[str, str]:
    css_path = DYGRAPHS_VENDOR_DIR / "dygraph.min.css"
    js_path = DYGRAPHS_VENDOR_DIR / "dygraph.min.js"
    if css_path.exists() and js_path.exists():
        css = _strip_source_map_comments(css_path.read_text(encoding="utf-8"))
        js = _strip_source_map_comments(
            js_path.read_text(encoding="utf-8"),
        ).replace("</script>", "<\\/script>")
        return (f"<style>\n{css}\n</style>", f"<script>\n{js}\n</script>")

    return (
        f'<link rel="stylesheet" href="{DYGRAPHS_CDN_CSS}">',
        f'<script src="{DYGRAPHS_CDN_JS}"></script>',
    )


def _strip_source_map_comments(text: str) -> str:
    lines = [line for line in text.splitlines() if "sourceMappingURL=" not in line]
    return "\n".join(lines)


def html_escape_json_string(value: str) -> str:
    return json.dumps(value)


def _ordered_y_groups(traces: list[AlignedTrace]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    groups: list[tuple[str, str]] = []
    for trace in traces:
        key = (trace.y_label, trace.y_unit)
        if key in seen:
            continue
        seen.add(key)
        groups.append(key)
    return groups


def _dedupe_labels(labels: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    output: list[str] = []
    for label in labels:
        count = counts.get(label, 0) + 1
        counts[label] = count
        output.append(label if count == 1 else f"{label} [{count}]")
    return output
