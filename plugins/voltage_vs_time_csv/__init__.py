from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData
from time_plot.units import (
    normalized_header_name,
    parse_header_column,
    time_unit_to_seconds_factor,
    voltage_unit_to_volts_factor,
)


def plugin_name() -> str:
    return "voltage-vs-time-csv"


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
    return [normalized_header_name(col) for col in columns] == ["time", "voltage"]


def parse(file_path: Path, options: dict[str, str] | None = None) -> list[SeriesData]:
    times: list[float] = []
    voltages: list[float] = []

    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != 2:
            msg = "Voltage vs. Time CSV requires two columns: time(...),voltage(...)"
            raise ValueError(msg)
        x_field, y_field = reader.fieldnames
        if [normalized_header_name(x_field), normalized_header_name(y_field)] != ["time", "voltage"]:
            msg = "Voltage vs. Time CSV requires columns named time(...) and voltage(...)"
            raise ValueError(msg)

        _, x_unit_in = parse_header_column(x_field)
        _, y_unit_in = parse_header_column(y_field)
        x_factor = time_unit_to_seconds_factor(x_unit_in)
        y_factor = voltage_unit_to_volts_factor(y_unit_in)

        for row in reader:
            times.append(float(row[x_field]) * x_factor)
            voltages.append(float(row[y_field]) * y_factor)

    return [SeriesData(
        source_name="Voltage vs. Time CSV",
        name=file_path.stem,
        x_label="Time",
        y_label=file_path.stem,
        x_unit="s",
        y_unit="v",
        y_unit_label="Voltage",
        x=np.asarray(times, dtype=np.float64),
        y=np.asarray(voltages, dtype=np.float64),
        x_display_prefix=None,
        y_display_prefix=None,
    )]
