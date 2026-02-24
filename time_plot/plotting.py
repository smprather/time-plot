from __future__ import annotations

import html
import json
from pathlib import Path

from time_plot.models import SeriesData


DYGRAPHS_CDN_JS = "https://cdn.jsdelivr.net/npm/dygraphs@2.2.1/dist/dygraph.min.js"
DYGRAPHS_CDN_CSS = "https://cdn.jsdelivr.net/npm/dygraphs@2.2.1/dist/dygraph.min.css"
DYGRAPHS_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor" / "dygraphs"


def write_dygraphs_html(series: SeriesData, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x_display_values, x_axis_label = series.x_display()
    y_display_values, y_axis_label = series.y_display()
    rows = [
        [float(x), float(y)]
        for x, y in zip(x_display_values.tolist(), y_display_values.tolist())
    ]
    html = _render_html(series, rows)
    html = html.replace("__X_AXIS_LABEL__", html_escape_json_string(x_axis_label))
    html = html.replace("__Y_AXIS_LABEL__", html_escape_json_string(y_axis_label))
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _render_html(series: SeriesData, rows: list[list[float]]) -> str:
    rows_json = json.dumps(rows)
    labels_json = json.dumps([series.x_label, series.y_label])
    title_json = json.dumps(series.source_name)
    xlabel_json = "__X_AXIS_LABEL__"
    ylabel_json = "__Y_AXIS_LABEL__"
    safe_title = html.escape(series.source_name)
    safe_source_name = html.escape(series.source_name)
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
      new Dygraph(plotEl, data, {{
        labels: labels,
        title: title,
        xlabel: xlabel,
        ylabel: ylabel,
        drawPoints: false,
        strokeWidth: 1.5,
        legend: "follow",
        animatedZooms: true
      }});
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
