from __future__ import annotations

import numpy as np

from time_plot.units import (
    normalized_header_name,
    parse_header_column,
    scale_for_display,
    time_unit_to_seconds_factor,
    voltage_unit_to_volts_factor,
)


def test_parse_header_column_and_normalization() -> None:
    name, unit = parse_header_column(" time(ns) ")
    assert name == "time"
    assert unit == "ns"
    assert normalized_header_name("Voltage(v)") == "voltage"


def test_unit_conversion_factors() -> None:
    assert time_unit_to_seconds_factor("ns") == 1e-9
    assert time_unit_to_seconds_factor("us") == 1e-6
    assert time_unit_to_seconds_factor("ms") == 1e-3
    assert time_unit_to_seconds_factor("s") == 1.0
    assert voltage_unit_to_volts_factor("mv") == 1e-3
    assert voltage_unit_to_volts_factor("v") == 1.0


def test_display_scaling_prefers_human_readable_units() -> None:
    x = np.asarray([0.0, 1e-6], dtype=np.float64)
    y = np.asarray([-0.9999987, 0.9999987], dtype=np.float64)

    x_scaled = scale_for_display(x, base_unit="s")
    y_scaled = scale_for_display(y, base_unit="v")

    assert x_scaled.display_unit == "us"
    assert y_scaled.display_unit == "v"
    np.testing.assert_allclose(x_scaled.scaled_values[-1], 1.0)
    np.testing.assert_allclose(y_scaled.scaled_values[-1], 0.9999987)

