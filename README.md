# AQUATOX Python (Stage-1 skeleton)

This repository contains a minimal, testable skeleton aligned to the UML for the
AQUATOX project:

- `Simulation`, `Environment`, `ODESolver` (Euler method)
- `StateVariable` hierarchy shells (`Nutrient`, `Detritus`, `Biota`, `Plant`, `Animal`)
- `ScenarioIO` JSON loader that reads environment metadata and initial state
  variables from a scenario file
- `pytest` based regression tests for the solver, environment water balance, and
  simple biota dynamics

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate  # or use conda/mamba
pip install -r requirements.txt

# Run unit tests to verify integrity
pytest -q

# Execute the sample Pyhäjärvi scenario for two days with 1 day timestep
python main.py --scenario tests/data/pyhajarvi_stub.json --days 2 --dt 1
```

The bundled `tests/data/pyhajarvi_stub.json` file demonstrates the JSON layout
needed by `ScenarioIO`. It includes:

- An `environment` block with scalar metadata (`volume`, `area`, depth fields)
  and simple inflow/outflow time series (arrays of `[ISO8601 date, value]`
  pairs).
- A `state_variables` list; for Stage-1 only the `nutrient` type is
  implemented. Each entry specifies the name, initial value, units, and
  nutrient form.

You can adapt the stub file as a template for larger Lake Pyhäjärvi datasets.

## Testing locally

All automated checks currently run via `pytest`:

```bash
pytest
```

The command executes the Stage-1 regression suite, ensuring that numerical
integration, water balance accounting, and scenario parsing remain stable. Run
this before committing or when adjusting the scenario JSON to guard against
regressions.
