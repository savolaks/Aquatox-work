# AQUATOX Python (savolainen2026)

This branch provides a focused, working AQUATOX implementation centered on
scenario parsing, forcing series handling, water-balance simulation, and
two export pathways:
1) all simulation variables to CSV, or
2) food web matrices to Excel.

The code is intentionally scoped and stable for batch runs and inspection.

## Features Included

### Scenario and Environment Handling
- Reads AQUATOX scenario text files (e.g., `Lake Pyhajarvi Finland_regression.txt`).
- Parses core environment properties:
  - lake volume, surface area, mean depth, max depth
- Parses inflow/outflow series and supports cyclic interpolation when the time
  range extends beyond available data.
- Supports forcing series and constants for:
  - temperature (epilimnion/hypolimnion)
  - wind
  - light
  - pH
  - TSS (total suspended solids)
- Interactive prompts are used only when a required value is missing from
  the scenario file.

### Simulation Core
- `Environment`, `Simulation`, and `ODESolver` are implemented.
- Water balance is updated using inflow/outflow each time step.
- Forcing values are injected into state variables where appropriate.

### State Variables
- Base `StateVariable` type plus:
  - `Nutrient`, `Detritus`, `Biota`, `Plant`, `Animal`
- Rate functions are placeholder/simple at this stage, but the structure
  supports future expansion.

### Food Web Support
- Food web is parsed primarily from in-scenario trophic interactions.
- External interspecies CSV (`AQ_Species_Models.cn`) is used only as a fallback.
- Export of 2D matrices:
  - preferences (raw and normalized)
  - egestion coefficients
- Excel output uses `.xlsx` or Excel-XML style via `write_excel`.

### Export Options (Only Two, Mutually Exclusive)
- Export all simulation variables to a single CSV file.
- Export the food web matrices to an Excel file.
- The CLI always asks for confirmation before writing output.

## Howto

### Preferred Setup (VSCode + Codes plugin)
This project works well with VSCode. A setup that matches the working style
for this branch:
1) Open the repository folder in VSCode.
2) Install and enable the "Codes" plugin (preferred by the author).
3) Use the built-in terminal for running commands.
4) (Optional) Select the Python interpreter from `.venv`.

### Environment Setup
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Run the Simulation (Only Two Output Modes)

Export all simulation variables to CSV:
```powershell
python main.py --all-series-csv all_series.csv
```

Export the food web matrices to Excel:
```powershell
python main.py --foodweb-excel foodweb_export.xlsx
```

After any command, you will be prompted:
```
Export outputs now? [y/N]
```
Answer `y` to write files, or press Enter to skip.

### Command Examples

Custom scenario input:
```powershell
python main.py -i "Lake Pyhajarvi Finland_regression.txt" --all-series-csv all_series.csv
```

Custom time window:
```powershell
python main.py --start 01/01/2010 --end 31/12/2010 --all-series-csv all_series.csv
```

Custom time step:
```powershell
python main.py --dt 0.5 --all-series-csv all_series.csv
```

Use a specific food web file:
```powershell
python main.py --food-web "AQ_Species_Models.cn" --foodweb-excel foodweb_export.xlsx
```

### Notes on Outputs
- The CSV export includes:
  - volume, inflow, outflow
  - epilimnion and hypolimnion temperature
  - wind, light, pH, TSS
- Temperature and pH in the CSV follow the time-varying series when present,
  otherwise they fall back to constants or derived values.
- Food web export will be skipped if no biota is initialized.

## Project Layout (Key Files)
- `main.py`: CLI entry point and export logic.
- `aquatox/core.py`: environment, solver, simulation loop, water balance.
- `aquatox/io_utils.py`: scenario parsing, series handling, CSV writing.
- `aquatox/state.py`: state variable hierarchy.

## Class Roles (Core Components)
- `Environment`: Holds lake geometry, forcing series, and helper accessors
  (inflow/outflow, temperature, wind, light, pH, TSS).
- `Simulation`: Orchestrates the time loop, updates state variables, applies
  forcing values, and advances the water balance.
- `ODESolver`: Integrates state variables in time (Euler method in this branch).
- `ScenarioIO`: Parses scenario files, loads time series, and writes CSV exports.
- `StateVariable` and subclasses: Represent modeled constituents (nutrients,
  detritus, plants, animals) and define rate-of-change interfaces.

## Reference Manuals (Time Series Generation)
The time series imported and exported by this code (e.g., inflow/outflow,
temperature, wind, light, pH, TSS) are produced according to AQUATOX
manual guidance. See:
- `AQUATOX Users Manual.html`
- `user-s-manual-3-1.pdf`

## Current Limitations
- Only Euler integration is implemented.
- The Euler solver has not been meaningfully tested in this branch because
  the current state-variable rates are placeholders and do not yet exercise
  the solver with dynamic processes.
- Many biological/chemical process rates are placeholders.
- Export is intentionally limited to one output mode at a time.
