from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np


_HEADER_RE = re.compile(r"^\s*([^(]+?)\s*(?:\(([^)]*)\))?\s*$")

SI_PREFIX_FACTORS: dict[str, float] = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "": 1.0,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
}

SI_PREFIX_ORDER = ["f", "p", "n", "u", "m", "", "k", "M", "G", "T"]


@dataclass(slots=True)
class DisplayScaling:
    scaled_values: np.ndarray
    display_unit: str
    prefix: str
    factor: float


def parse_header_column(column_name: str) -> tuple[str, str | None]:
    match = _HEADER_RE.match(column_name)
    if match is None:
        msg = f"Invalid header column: {column_name!r}"
        raise ValueError(msg)
    name = match.group(1).strip()
    unit = match.group(2)
    if unit is not None:
        unit = unit.strip()
        if not unit:
            unit = None
    return name, unit


def normalized_header_name(column_name: str) -> str:
    name, _ = parse_header_column(column_name)
    return name.strip().lower()


def time_unit_to_seconds_factor(unit: str | None) -> float:
    if unit is None:
        msg = "Time column must include a unit in parentheses"
        raise ValueError(msg)

    normalized = unit.strip()
    lowered = normalized.lower()
    if lowered in {"s", "sec", "secs", "second", "seconds"}:
        return 1.0
    if lowered in {"m", "min", "mins", "minute", "minutes"}:
        return 60.0

    # SI-prefixed seconds (ASCII prefixes, e.g. ms, us, ns)
    if normalized.endswith("s"):
        prefix = normalized[:-1]
        if prefix in SI_PREFIX_FACTORS:
            return SI_PREFIX_FACTORS[prefix]
        if prefix.lower() == "k":
            return SI_PREFIX_FACTORS["k"]

    msg = f"Unsupported time unit: {unit!r}"
    raise ValueError(msg)


def voltage_unit_to_volts_factor(unit: str | None) -> float:
    if unit is None:
        msg = "Voltage column must include a unit in parentheses"
        raise ValueError(msg)

    normalized = unit.strip()
    lowered = normalized.lower()
    if lowered in {"v", "volt", "volts"}:
        return 1.0

    if normalized.endswith(("v", "V")):
        prefix = normalized[:-1]
        if prefix in SI_PREFIX_FACTORS:
            return SI_PREFIX_FACTORS[prefix]
        if prefix.lower() == "k":
            return SI_PREFIX_FACTORS["k"]

    msg = f"Unsupported voltage unit: {unit!r}"
    raise ValueError(msg)


def current_unit_to_amps_factor(unit: str | None) -> float:
    if unit is None:
        msg = "Current column must include a unit in parentheses"
        raise ValueError(msg)

    normalized = unit.strip()
    lowered = normalized.lower()
    if lowered in {"a", "amp", "amps"}:
        return 1.0

    if normalized.endswith(("a", "A")):
        prefix = normalized[:-1]
        if prefix in SI_PREFIX_FACTORS:
            return SI_PREFIX_FACTORS[prefix]
        if prefix.lower() == "k":
            return SI_PREFIX_FACTORS["k"]

    msg = f"Unsupported current unit: {unit!r}"
    raise ValueError(msg)


def scale_for_display(
    values: np.ndarray,
    *,
    base_unit: str,
    forced_prefix: str | None = None,
) -> DisplayScaling:
    arr = np.asarray(values, dtype=np.float64)

    prefix = forced_prefix if forced_prefix is not None else auto_si_prefix(arr)
    if prefix not in SI_PREFIX_FACTORS:
        msg = f"Unsupported SI prefix for display: {prefix!r}"
        raise ValueError(msg)

    factor = SI_PREFIX_FACTORS[prefix]
    scaled = arr / factor
    return DisplayScaling(
        scaled_values=scaled,
        display_unit=f"{prefix}{base_unit}",
        prefix=prefix,
        factor=factor,
    )


def auto_si_prefix(values: np.ndarray) -> str:
    arr = np.asarray(values, dtype=np.float64)
    finite = np.abs(arr[np.isfinite(arr)])
    finite = finite[finite > 0]
    if finite.size == 0:
        return ""

    magnitude = float(np.max(finite))
    best_prefix = ""
    best_score = float("inf")

    for prefix in SI_PREFIX_ORDER:
        factor = SI_PREFIX_FACTORS[prefix]
        scaled = magnitude / factor
        if scaled <= 0:
            continue

        if 0.5 <= scaled < 1000.0:
            # Prefer a max value near 1 for cleaner unit choices (e.g. 1 us over 1000 ns).
            score = abs(np.log10(scaled) - 0.0)
        elif scaled < 1.0:
            # Penalize too-small values heavily.
            score = 10.0 + abs(np.log10(scaled) - 0.0)
        else:
            # Penalize too-large values heavily.
            score = 10.0 + abs(np.log10(scaled) - 3.0)
        if score < best_score:
            best_score = score
            best_prefix = prefix

    return best_prefix
