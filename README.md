# AQUATOX Python (Stage-1 skeleton)

This is a minimal, testable skeleton aligned to the committed UML:
- `Simulation`, `Environment`, `ODESolver` (Euler)
- `StateVariable` hierarchy shells (`Nutrient`, `Detritus`, `Biota`, `Plant`, `Animal`)
- `ScenarioIO` stub returning a tiny synthetic scenario
- PyTest tests for solver, environment water balance, and simple biota dynamics

## Quickstart
```bash
python -m venv .venv && . .venv/bin/activate  # or use conda
pip install -r requirements.txt
pytest -q
