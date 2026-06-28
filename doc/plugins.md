# Plugins

## Voltage/Current vs. Time CSV

- Format name: `Voltage/Current vs. Time`
- Plugin ID: `voltage-or-current-vs-time`
- Plugin package directory: `plugins/voltage_or_current_vs_time`
- Base format: CSV with header names `time(<unit>)`, and `voltage(<unit>)` or `current(<unit>)`
- Units are stored in header parentheticals (for example `time(ns)`)
- Recognition rule:
  - filename must end in `.csv`
  - first line must have column names `time(...)`, and `voltage(...)` or `current(...)`
  - ignore parenthetical units when checking support
  - Example recognized header: `time(ns),voltage(v)`
- Fallback `data_source_name` is the basename of the path with the .csv extension removed.
- `data_set_name` is the file stem (same as the `data_source_name` for this single-series plugin).
- `data_set_label` is the file stem.
- Long unit name is "Voltage" in the case of a `voltage` column header, or "Amps" in the case of a `current`
  column header.
  - Short unit name is "v" or "a", respectively.

## SPICE PWL Plugin

- Format name: `SPICE PWL`
- Plugin ID: `spice-pwl`
- Plugin package directory: `plugins/spice_pwl`
- Parses SPICE netlists containing PWL (piecewise-linear) voltage or current sources.
  - It is an error for a SPICE PWL file to define both, current sources, and voltage sources.
- Matching rule: all matching rules mentioned below are case-insensitive.
- Recognition rule:
  - First non-comment (`*`), non-empty line must start with `i` or `v`.
  - That line, the whitespace-based line-split must contain `pwl` at position index >= 3.
- Line continuations: lines starting with `+` are appended to the previous logical line before parsing.
- Source type determines y-unit: `v` prefix → y_unit `v`, `i` prefix → y_unit `a`.
  - Long label is "Volts" if v-type source.
  - Long label is "Amps" if i-type source.
- PWL values are time-value pairs with SPICE numeric suffixes (`n`=1e-9, `m`=1e-3, `u`=1e-6, `k`=1e3,
  `meg`=1e6, etc.).
- Time values are converted to seconds; y values are stored in base units.
- Each PWL source in the file produces one `data_set`
- Fallback `data_source_name` is the basename of the path with the file extension removed.
- The `data_set_name` is determined by the parser option `naming_method`.
  - The possible option values are `element_name` and `positive_node_name`.
  - The default is `element_name`.
  - When `naming_method` is `element_name`, the `data_set_name` is the full SPICE element name (first token).
    Example: `ifoo bar 0 pwl 0 0` → `data_set_name` is `ifoo`.
  - When `naming_method` is `positive_node_name`, the `data_set_name` is the positive terminal name
    (second token).
    Example: `ifoo bar 0 pwl 0 0` → `data_set_name` is `bar`.

## VCD Logic Plugin

- Format name: `VCD Logic`
- Plugin ID: `vcd`
- Plugin package directory: `plugins/vcd`
- Parses scalar 1-bit signals from Value Change Dump files.
- Recognition rule:
  - filename must end in `.vcd`
  - file must contain `$enddefinitions`
- `$timescale` is required and is converted to seconds.
- `$scope` and `$upscope` build hierarchical series names.
  - Example: `$scope module top $end`, `$var wire 1 ! clk $end` -> `top.clk`
- Only `$var ... 1 ... $end` definitions are listed and parsed.
  - Vector/bus definitions are skipped.
- Supported scalar value changes:
  - `0<id>` -> `0.0`
  - `1<id>` -> `1.0`
  - `z<id>` -> numeric `NaN`, rendered as an orange midline
  - `x<id>` -> numeric `NaN`, rendered as red low/high rails
- Duplicate changes at the same timestamp keep the final value for that signal.
- Each parsed signal has `y_unit` set to `logic`, `y_unit_label` set to `Logic`, and `sample_mode` set to `step`.
- Each parsed signal also sets `logic_states` so the renderer can distinguish `x` and `z` from ordinary gaps.
- Step-mode logic traces are aligned by previous-held value, not linear interpolation.
- Logic traces render as separate stacked lanes with vertical edges at exact VCD timestamps and no `Logic` y-axis title.
- Logic legend rows group all helper lines for one signal and display `0`/`1`/`X`/`Z`.
- Logic plots omit numeric summary statistics, because `x`/`z` states are not ordinary numeric values.
