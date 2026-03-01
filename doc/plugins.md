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
