from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData

# Three tab-separated fields with optional surrounding whitespace:
# integer index, scientific-notation float (time in seconds), float (current in amps).
_FIRST_LINE_RE = re.compile(
    r"^\s*\d+\t\s*[+-]?\d+(?:\.\d+)?[eE][+-]?\d+\t\s*[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*$"
)


def plugin_name() -> str:
    return "cadence-dynamic-power-totalcurrent"


def identify(file_path: Path) -> bool:
    if file_path.suffix.lower() != ".totalcurrent":
        return False
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline()
    except (OSError, UnicodeDecodeError):
        return False
    return bool(_FIRST_LINE_RE.match(first_line))


def parse(file_path: Path, options: dict[str, str] | None = None) -> list[SeriesData]:
    times: list[float] = []
    values: list[float] = []

    with file_path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            fields = [f.strip() for f in line.split("\t")]
            if len(fields) != 3:
                msg = f"{file_path}:{lineno}: expected 3 fields, got {len(fields)}"
                raise ValueError(msg)
            times.append(float(fields[1]))
            values.append(float(fields[2]))

    if not times:
        msg = f"No data rows found in {file_path}"
        raise ValueError(msg)

    return [SeriesData(
        source_name="Cadence Dynamic Power Total Current",
        name=file_path.stem,
        x_label="Time",
        y_label=file_path.stem,
        x_unit="s",
        y_unit="a",
        y_unit_label="Amps",
        x=np.asarray(times, dtype=np.float64),
        y=np.asarray(values, dtype=np.float64),
        x_display_prefix=None,
        y_display_prefix=None,
    )]
