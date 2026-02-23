from __future__ import annotations

import csv
import math
from pathlib import Path


def write_voltage_time_sample_csv(output_path: Path, points: int = 1000) -> Path:
    if points < 2:
        msg = "points must be >= 2"
        raise ValueError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_duration_ns = 1000.0  # 1 us total
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time(ns)", "voltage"])
        for index in range(points):
            t_ns = (index / (points - 1)) * total_duration_ns
            voltage_mv = math.sin((2.0 * math.pi * t_ns) / total_duration_ns)
            writer.writerow([f"{t_ns:.12f}", f"{voltage_mv:.12f}"])

    return output_path

