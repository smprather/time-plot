from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.models import SeriesData


def short_description() -> str:
    return "2-column whitespace-separated .txt: time(s), current(a), no header"


def long_description() -> str:
    return """\
Plugin: txt-file
Matches: .txt files whose first line contains at least one floating-point number

Parses headerless 2-column whitespace-separated files.
  Column 1: time in seconds
  Column 2: current in amps

The series name is the filename stem.\
"""


def plugin_name() -> str:
    return "txt-file"


def identify(file_path: Path) -> bool:
    if file_path.suffix.lower() != ".txt":
        return False
    try:
        with file_path.open("r", encoding="utf-8") as fh:
            first_line = fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return False
    parts = first_line.split()
    if not parts:
        return False
    try:
        float(parts[0])
    except ValueError:
        return False
    return True


def parse(
    file_path: Path,
    options: dict[str, str] | None = None,
    selected: list[str] | None = None,
) -> list[SeriesData]:
    times: list[float] = []
    values: list[float] = []

    with file_path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                msg = f"{file_path}:{lineno}: expected 2 columns, got {len(parts)}"
                raise ValueError(msg)
            times.append(float(parts[0]))
            values.append(float(parts[1]))

    return [
        SeriesData(
            source_name="Text File",
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
        )
    ]
