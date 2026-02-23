from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData


EXPECTED_HEADER = "time(ns),voltage"


def plugin_name() -> str:
    return "voltage-time-csv"


def identify(file_path: Path) -> bool:
    try:
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            first_line = handle.readline().strip()
    except (OSError, UnicodeDecodeError):
        return False
    return first_line == EXPECTED_HEADER


def parse(file_path: Path) -> SeriesData:
    times: list[float] = []
    voltages: list[float] = []

    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["time(ns)", "voltage"]:
            msg = "Voltage vs. Time CSV header must be exactly 'time(ns),voltage'"
            raise ValueError(msg)
        for row in reader:
            times.append(float(row["time(ns)"]))
            voltages.append(float(row["voltage"]))

    return SeriesData(
        source_name="Voltage vs. Time CSV",
        x_label="Time",
        y_label="Voltage",
        x_unit="ns",
        y_unit="mV",
        x=np.asarray(times, dtype=np.float64),
        y=np.asarray(voltages, dtype=np.float64),
    )

