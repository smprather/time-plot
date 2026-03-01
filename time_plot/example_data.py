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
    amplitude: float
    waveform: str  # "sine" | "cosine"
    unit_type: str  # "voltage" | "current"


EXAMPLE_WAVES = (
    ExampleWaveSpec(
        filename="sine.csv",
        points=1000,
        duration_us=1.0,
        cycles=2.0,
        amplitude=1.0,
        waveform="sine",
        unit_type="voltage",
    ),
    ExampleWaveSpec(
        filename="cosine.csv",
        points=800,
        duration_us=2.0,
        cycles=3.0,
        amplitude=2.0,
        waveform="cosine",
        unit_type="current",
    ),
)

_CSV_HEADERS = {
    "voltage": ("time(ns)", "voltage(mv)"),
    "current": ("time(ns)", "current(ma)"),
}


def write_csv_example(
    output_path: Path,
    *,
    points: int = 1000,
    duration_us: float = 1.0,
    cycles: float = 1.0,
    amplitude: float = 1.0,
    waveform: str = "sine",
    unit_type: str = "voltage",
) -> Path:
    if points < 2:
        msg = "points must be >= 2"
        raise ValueError(msg)
    if duration_us <= 0:
        msg = "duration_us must be > 0"
        raise ValueError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = _CSV_HEADERS.get(unit_type)
    if header is None:
        msg = f"Unsupported unit_type: {unit_type}"
        raise ValueError(msg)

    total_duration_ns = duration_us * 1000.0
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(header))
        for index in range(points):
            t_ns = (index / (points - 1)) * total_duration_ns
            phase = (2.0 * math.pi * cycles * t_ns) / total_duration_ns
            if waveform == "sine":
                value = amplitude * math.sin(phase)
            elif waveform == "cosine":
                value = amplitude * math.cos(phase)
            else:
                msg = f"Unsupported waveform: {waveform}"
                raise ValueError(msg)
            value_milli = value * 1000.0
            writer.writerow([f"{t_ns:.12f}", f"{value_milli:.12f}"])

    return output_path


def write_spice_pwl_example(output_path: Path, *, num_points: int = 300, duration_us: float = 2.0) -> Path:
    """Generate a SPICE PWL file with 2 voltage square-wave sources."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sources = [
        {"name": "vclk_0p75us", "node": "clk_0p75us", "vlow": 0.0, "vhigh": 1.0, "trise": 0.05e-6, "tfall": 0.05e-6, "period": 0.75e-6},
        {"name": "vclk_1p00us", "node": "clk_1p00us", "vlow": 0.0, "vhigh": 0.9, "trise": 0.07e-6, "tfall": 0.07e-6, "period": 1.0e-6},
    ]

    total_duration_s = duration_us * 1e-6
    dt = total_duration_s / (num_points - 1)

    lines: list[str] = []
    for src in sources:
        pairs: list[str] = []
        for i in range(num_points):
            t = i * dt
            t_in_period = t % src["period"]
            trise = src["trise"]
            tfall = src["tfall"]
            vlow = src["vlow"]
            vhigh = src["vhigh"]
            period = src["period"]
            half = period / 2.0

            if t_in_period < trise:
                v = vlow + (vhigh - vlow) * (t_in_period / trise)
            elif t_in_period < half:
                v = vhigh
            elif t_in_period < half + tfall:
                v = vhigh - (vhigh - vlow) * ((t_in_period - half) / tfall)
            else:
                v = vlow

            pairs.append(f"{t:.10g} {v:.10g}")

        pwl_data = "\n+ ".join(pairs)
        lines.append(f"{src['name']} {src['node']} 0 pwl {pwl_data}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def write_example_data_files(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in EXAMPLE_WAVES:
        path = output_dir / spec.filename
        write_csv_example(
            path,
            points=spec.points,
            duration_us=spec.duration_us,
            cycles=spec.cycles,
            amplitude=spec.amplitude,
            waveform=spec.waveform,
            unit_type=spec.unit_type,
        )
        written.append(path)
    written.append(write_spice_pwl_example(output_dir / "spice_pwl.spi"))
    return written
