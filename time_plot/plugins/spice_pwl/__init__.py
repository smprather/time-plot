from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from time_plot.models import SeriesData

_SPICE_SUFFIXES: dict[str, float] = {
    "meg": 1e6,
    "t": 1e12,
    "g": 1e9,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}

# Longest-first so "meg" is tried before "m".
_SUFFIX_ORDER = sorted(_SPICE_SUFFIXES, key=len, reverse=True)


def short_description() -> str:
    return "SPICE netlist PWL voltage/current sources (.spi, .sp, .cir, .net, .spice)"


def long_description() -> str:
    return """\
Plugin: spice-pwl
Matches: .spi  .sp  .cir  .net  .spice

Parses piecewise-linear (PWL) voltage and current source statements from SPICE
netlists.  Each source becomes one series.

Supported syntax (case-insensitive):
  V<name> ... PWL( t0 v0  t1 v1 ... )
  I<name> ... PWL( t0 i0  t1 i1 ... )

Options (--parser-options key=value):
  naming_method   Controls how the series name is derived from the source name.
                  Values:
                    auto      Strip leading V/I, use remainder (default)
                    full      Keep full source name including V/I prefix
                    instance  Use the instance name only

Units: voltage sources → V, current sources → A.
Time axis is always seconds.\
"""


def plugin_name() -> str:
    return "spice-pwl"


def identify(file_path: Path) -> bool:
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("*"):
                    continue
                first_char = stripped[0].lower()
                if first_char not in ("i", "v"):
                    return False
                tokens = stripped.lower().split()
                return any("pwl" in tokens[idx] for idx in range(3, len(tokens)))
    except (OSError, UnicodeDecodeError):
        return False
    return False


def parse(file_path: Path, options: dict[str, str] | None = None, selected: list[str] | None = None) -> list[SeriesData]:
    raw_lines = file_path.read_text(encoding="utf-8").splitlines()
    logical_lines = _aggregate_continuations(raw_lines)
    opts = options or {}
    naming_method = opts.get("naming_method", "element_name")
    if naming_method not in {"element_name", "positive_node_name"}:
        msg = f"Invalid naming_method: {naming_method!r} (expected 'element_name' or 'positive_node_name')"
        raise ValueError(msg)

    results: list[SeriesData] = []
    source_types: set[str] = set()
    for line in logical_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        first_char = stripped[0].lower()
        if first_char not in ("i", "v"):
            continue

        tokens = stripped.split()
        pwl_idx: int | None = None
        for idx in range(3, len(tokens)):
            if "pwl" in tokens[idx].lower():
                pwl_idx = idx
                break
        if pwl_idx is None:
            continue

        source_types.add(first_char)
        if len(source_types) > 1:
            msg = f"SPICE PWL file contains both voltage and current sources: {file_path}"
            raise ValueError(msg)

        element_name = tokens[0]
        if naming_method == "positive_node_name":
            data_set_name = tokens[1]
        else:
            data_set_name = element_name
        y_unit = "v" if first_char == "v" else "a"
        y_unit_label = "Volts" if first_char == "v" else "Amps"

        # Collect everything from the pwl token onward, strip the "pwl" keyword
        # and any parentheses, then split into flat value tokens.
        pwl_rest = re.sub(r"(?i)pwl", "", tokens[pwl_idx])
        tail = pwl_rest + " " + " ".join(tokens[pwl_idx + 1 :])
        tail = tail.replace("(", " ").replace(")", " ")
        value_tokens = tail.split()

        if len(value_tokens) % 2 != 0:
            msg = f"PWL source {element_name}: odd number of values (expected time-value pairs)"
            raise ValueError(msg)

        times: list[float] = []
        values: list[float] = []
        for i in range(0, len(value_tokens), 2):
            times.append(_parse_spice_number(value_tokens[i]))
            values.append(_parse_spice_number(value_tokens[i + 1]))

        results.append(
            SeriesData(
                source_name="SPICE PWL",
                name=data_set_name,
                x_label="Time",
                y_label=data_set_name,
                x_unit="s",
                y_unit=y_unit,
                y_unit_label=y_unit_label,
                x=np.asarray(times, dtype=np.float64),
                y=np.asarray(values, dtype=np.float64),
            ),
        )

    if not results:
        msg = f"No PWL sources found in {file_path}"
        raise ValueError(msg)

    return results


def _aggregate_continuations(raw_lines: list[str]) -> list[str]:
    logical: list[str] = []
    for line in raw_lines:
        if line.startswith("+") and logical:
            logical[-1] = logical[-1] + " " + line[1:]
        else:
            logical.append(line)
    return logical


def _parse_spice_number(token: str) -> float:
    token = token.strip()
    try:
        return float(token)
    except ValueError:
        pass

    lower = token.lower()
    for suffix in _SUFFIX_ORDER:
        if lower.endswith(suffix):
            num_part = token[: len(token) - len(suffix)]
            try:
                return float(num_part) * _SPICE_SUFFIXES[suffix]
            except ValueError:
                continue

    msg = f"Cannot parse SPICE number: {token!r}"
    raise ValueError(msg)
