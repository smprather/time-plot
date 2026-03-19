from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData
from time_plot.units import (
    current_unit_to_amps_factor,
    normalized_header_name,
    parse_header_column,
    time_unit_to_seconds_factor,
    voltage_unit_to_volts_factor,
)


def plugin_name() -> str:
    return "voltage-or-current-vs-time"


def identify(file_path: Path) -> bool:
    if file_path.suffix.lower() != ".csv":
        return False
    try:
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            first_line = handle.readline().strip()
    except (OSError, UnicodeDecodeError):
        return False
    if not first_line:
        return False
    try:
        columns = next(csv.reader([first_line]))
    except csv.Error:
        return False
    if len(columns) != 2:
        return False
    names = [normalized_header_name(col) for col in columns]
    return names[0] == "time" and names[1] in {"voltage", "current"}


def parse(file_path: Path, options: dict[str, str] | None = None) -> list[SeriesData]:
    times: list[float] = []
    values: list[float] = []

    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != 2:
            msg = "CSV requires two columns: time(...) and voltage(...) or current(...)"
            raise ValueError(msg)
        x_field, y_field = reader.fieldnames
        y_header_name = normalized_header_name(y_field)
        if normalized_header_name(x_field) != "time" or y_header_name not in {"voltage", "current"}:
            msg = "CSV requires columns named time(...) and voltage(...) or current(...)"
            raise ValueError(msg)

        _, x_unit_in = parse_header_column(x_field)
        _, y_unit_in = parse_header_column(y_field)
        x_factor = time_unit_to_seconds_factor(x_unit_in)

        if y_header_name == "voltage":
            y_factor = voltage_unit_to_volts_factor(y_unit_in)
            y_unit = "v"
            y_unit_label = "Voltage"
        else:
            y_factor = current_unit_to_amps_factor(y_unit_in)
            y_unit = "a"
            y_unit_label = "Amps"

        for row in reader:
            times.append(float(row[x_field]) * x_factor)
            values.append(float(row[y_field]) * y_factor)

    return [SeriesData(
        source_name="Voltage/Current vs. Time",
        name=file_path.stem,
        x_label="Time",
        y_label=file_path.stem,
        x_unit="s",
        y_unit=y_unit,
        y_unit_label=y_unit_label,
        x=np.asarray(times, dtype=np.float64),
        y=np.asarray(values, dtype=np.float64),
        x_display_prefix=None,
        y_display_prefix=None,
    )]
