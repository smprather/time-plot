from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import NamedTuple


class ExampleWaveSpec(NamedTuple):
    filename: str
    points: int
    duration_us: float
    cycles: float
    amplitude_v: float
    waveform: str  # "sine" | "cosine"


EXAMPLE_WAVES = (
    ExampleWaveSpec(
        filename="sine.csv",
        points=1000,
        duration_us=1.0,
        cycles=2.0,
        amplitude_v=1.0,
        waveform="sine",
    ),
    ExampleWaveSpec(
        filename="cosine.csv",
        points=800,
        duration_us=2.0,
        cycles=3.0,
        amplitude_v=2.0,
        waveform="cosine",
    ),
)


def write_voltage_time_sample_csv(
    output_path: Path,
    *,
    points: int = 1000,
    duration_us: float = 1.0,
    cycles: float = 1.0,
    amplitude_v: float = 1.0,
    waveform: str = "sine",
) -> Path:
    if points < 2:
        msg = "points must be >= 2"
        raise ValueError(msg)
    if duration_us <= 0:
        msg = "duration_us must be > 0"
        raise ValueError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_duration_ns = duration_us * 1000.0
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time(ns)", "voltage(mv)"])
        for index in range(points):
            t_ns = (index / (points - 1)) * total_duration_ns
            phase = (2.0 * math.pi * cycles * t_ns) / total_duration_ns
            if waveform == "sine":
                voltage_v = amplitude_v * math.sin(phase)
            elif waveform == "cosine":
                voltage_v = amplitude_v * math.cos(phase)
            else:
                msg = f"Unsupported waveform: {waveform}"
                raise ValueError(msg)
            voltage_mv = voltage_v * 1000.0
            writer.writerow([f"{t_ns:.12f}", f"{voltage_mv:.12f}"])

    return output_path


def write_example_data_files(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in EXAMPLE_WAVES:
        path = output_dir / spec.filename
        write_voltage_time_sample_csv(
            path,
            points=spec.points,
            duration_us=spec.duration_us,
            cycles=spec.cycles,
            amplitude_v=spec.amplitude_v,
            waveform=spec.waveform,
        )
        written.append(path)
    return written
