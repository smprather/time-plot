# Example Data Generation

- Do not expose the data generation script to the end user. It is only meant to be executed by the developer,
  including a coding agent.
  - Agent should execute the script any time updates are made to the script.
- Script executable name: `generate_example_data`

## Output

- Write all outputs to the `example_data` directory.
- Required files:
  - `sine.csv`
    - 1000 points spanning 1.0 microsecond
    - 2 cycles of sine wave
    - amplitude 1 Volt (stored as `mv`)
  - `cosine.csv`
    - 800 points spanning 2.0 microseconds
    - 3 cycles of cosine wave
    - amplitude = 2 Amps (stored as `ma`)
  - `spice_pwl.spi`
    - 300 points spanning 2.0 microseconds
    - SPICE formatted PWL data representing 2 pwl voltage sources
      - First
        - A square wave sequence with amplitude of 1 volt
        - Vlow=0.0, Vhigh=1.0, Trise/fall=0.05us, period=0.75us
        - Voltage source is named clk_0p75us
      - Second
        - A square wave sequence with amplitude of 1 volt
        - Vlow=0.0, Vhigh=0.9, Trise/fall=0.07us, period=1.00us
        - Voltage source is named clk_1p00us
