from __future__ import annotations

from pathlib import Path

import numpy as np

from time_plot.models import SeriesData
from time_plot.units import parse_seconds


def short_description() -> str:
    return "VCD logic waveform files (.vcd), scalar 1-bit signals"


def long_description() -> str:
    return """\
Plugin: vcd
Matches: .vcd files containing $enddefinitions

Parses scalar 1-bit signals from Value Change Dump files. Signal names are
hierarchical, for example top.clk or tb.uart.rx.

Supported value changes:
  0<id>  -> 0
  1<id>  -> 1
  x<id>  -> unknown, rendered as red high/low rails
  z<id>  -> high impedance, rendered as orange midline

Vector/bus changes are not plotted by this first-pass plugin. Time values are
converted to seconds from the file's $timescale. Logic traces render as step
signals so edges occur at the exact VCD timestamp.\
"""


def plugin_name() -> str:
    return "vcd"


def identify(file_path: Path) -> bool:
    if file_path.suffix.lower() != ".vcd":
        return False
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            return any("$enddefinitions" in line for line in handle)
    except (OSError, UnicodeDecodeError):
        return False


def list_series(file_path: Path, options: dict[str, str] | None = None) -> list[str]:
    del options
    definitions = _read_definitions(file_path)
    return definitions.names


def parse(file_path: Path, options: dict[str, str] | None = None, selected: list[str] | None = None) -> list[SeriesData]:
    del options
    definitions = _read_definitions(file_path)
    selected_names = set(selected) if selected is not None else set(definitions.names)
    wanted_names = [name for name in definitions.names if name in selected_names]
    if not wanted_names:
        return []

    events: dict[str, list[tuple[float, float, str]]] = {name: [] for name in wanted_names}
    code_to_names = {
        code: [name for name in names if name in selected_names]
        for code, names in definitions.code_to_names.items()
    }

    current_time = 0.0
    end_time = 0.0
    in_value_section = False

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not in_value_section:
            if line.startswith("$enddefinitions"):
                in_value_section = True
            continue
        if line.startswith("$dumpvars") or line == "$end":
            continue
        if line.startswith("#"):
            current_time = int(line[1:].strip()) * definitions.timescale_seconds
            end_time = max(end_time, current_time)
            continue
        value_change = _parse_scalar_value_change(line)
        if value_change is None:
            continue
        value, state, code = value_change
        for name in code_to_names.get(code, []):
            _append_event(events[name], current_time, value, state)

    results: list[SeriesData] = []
    for name in wanted_names:
        signal_events = events[name]
        if not signal_events:
            continue
        last_time, last_value, last_state = signal_events[-1]
        if end_time > last_time:
            signal_events.append((end_time, last_value, last_state))
        x = np.asarray([time for time, _, _ in signal_events], dtype=np.float64)
        y = np.asarray([value for _, value, _ in signal_events], dtype=np.float64)
        logic_states = np.asarray([state for _, _, state in signal_events], dtype=np.str_)
        results.append(
            SeriesData(
                source_name="VCD Logic",
                name=name,
                x_label="Time",
                y_label=name,
                x_unit="s",
                y_unit="logic",
                y_unit_label="Logic",
                x=x,
                y=y,
                sample_mode="step",
                logic_states=logic_states,
            ),
        )

    if not results:
        msg = f"No scalar VCD value changes found in {file_path}"
        raise ValueError(msg)
    return results


class _Definitions:
    def __init__(
        self,
        *,
        timescale_seconds: float,
        names: list[str],
        code_to_names: dict[str, list[str]],
    ) -> None:
        self.timescale_seconds = timescale_seconds
        self.names = names
        self.code_to_names = code_to_names


def _read_definitions(file_path: Path) -> _Definitions:
    lines = file_path.read_text(encoding="utf-8").splitlines()
    timescale_seconds: float | None = None
    scopes: list[str] = []
    names: list[str] = []
    code_to_names: dict[str, list[str]] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if line.startswith("$enddefinitions"):
            break
        if line.startswith("$timescale"):
            statement, idx = _collect_statement(lines, idx)
            timescale_seconds = _parse_timescale(statement)
            continue
        if line.startswith("$scope"):
            tokens = line.split()
            if len(tokens) >= 4:
                scopes.append(tokens[2])
            idx += 1
            continue
        if line.startswith("$upscope"):
            if scopes:
                scopes.pop()
            idx += 1
            continue
        if line.startswith("$var"):
            statement, idx = _collect_statement(lines, idx)
            parsed = _parse_var(statement, scopes)
            if parsed is not None:
                code, name = parsed
                names.append(name)
                code_to_names.setdefault(code, []).append(name)
            continue
        idx += 1

    if timescale_seconds is None:
        msg = f"VCD file missing $timescale: {file_path}"
        raise ValueError(msg)

    return _Definitions(
        timescale_seconds=timescale_seconds,
        names=names,
        code_to_names=code_to_names,
    )


def _collect_statement(lines: list[str], start: int) -> tuple[str, int]:
    parts: list[str] = []
    idx = start
    while idx < len(lines):
        parts.append(lines[idx].strip())
        if "$end" in lines[idx].split():
            return " ".join(parts), idx + 1
        idx += 1
    return " ".join(parts), idx


def _parse_timescale(statement: str) -> float:
    tokens = statement.split()
    body = [token for token in tokens[1:] if token != "$end"]
    if len(body) == 1:
        text = body[0]
    elif len(body) >= 2:
        text = f"{body[0]}{body[1]}"
    else:
        msg = f"Invalid VCD $timescale statement: {statement!r}"
        raise ValueError(msg)
    return parse_seconds(text)


def _parse_var(statement: str, scopes: list[str]) -> tuple[str, str] | None:
    tokens = statement.split()
    if len(tokens) < 6 or tokens[0] != "$var":
        return None
    try:
        size = int(tokens[2])
    except ValueError:
        return None
    if size != 1:
        return None
    code = tokens[3]
    reference_tokens = tokens[4:-1]
    if not reference_tokens:
        return None
    reference = "".join(reference_tokens)
    name = ".".join([*scopes, reference]) if scopes else reference
    return code, name


def _parse_scalar_value_change(line: str) -> tuple[float, str, str] | None:
    prefix = line[0].lower()
    if prefix not in {"0", "1", "x", "z"}:
        return None
    code = line[1:].strip()
    if not code:
        return None
    if prefix == "0":
        return 0.0, "0", code
    if prefix == "1":
        return 1.0, "1", code
    return float("nan"), prefix, code


def _append_event(
    events: list[tuple[float, float, str]],
    time_seconds: float,
    value: float,
    state: str,
) -> None:
    if events and events[-1][0] == time_seconds:
        events[-1] = (time_seconds, value, state)
        return
    if events and _same_state(events[-1][2], state):
        return
    events.append((time_seconds, value, state))


def _same_state(left: str, right: str) -> bool:
    return left == right
