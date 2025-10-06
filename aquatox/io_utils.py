# aquatox/io_utils.py
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from .core import Environment
from .state import StateVariable, Nutrient

def _parse_timeseries(entries) -> Dict[datetime, float]:
    """Convert ``[[iso_date, value], ...]`` rows into a datetime keyed mapping.

    Parameters
    ----------
    entries:
        JSON-compatible list containing two-element ``[date, value]`` pairs.
        The helper performs strict validation so that scenario files fail fast
        when a typo slips in.
    """
    series: Dict[datetime, float] = {}
    for item in entries:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("Time series entries must be [date, value]")
        date_str, value = item
        try:
            ts = datetime.fromisoformat(date_str)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid date in time series: {date_str!r}") from exc
        series[ts] = float(value)
    return series


def _require(container, key):
    """Return a required key from a mapping or raise a descriptive error."""
    if key not in container:
        raise ValueError(f"Scenario file missing required field '{key}'")
    return container[key]


class ScenarioIO:
    """Helpers for reading and writing AQUATOX scenario inputs and outputs.

    The class centralises the JSON schema used throughout the Stage-1 tooling.
    Having a single location for validation logic avoids scattering ad-hoc
    checks across the codebase and mirrors the responsibilities outlined in the
    original AQUATOX UML documentation.
    """
    @staticmethod
    def load_initial_conditions(file: str) -> tuple[Environment, list[StateVariable]]:
        """Load environment and initial state variables from a JSON scenario.

        Parameters
        ----------
        file:
            Path to the JSON scenario definition on disk.  The structure is
            intentionally narrow for Stage-1 but the loader leaves room for
            extension by returning ``Environment`` and ``StateVariable`` objects.
        """
        scenario_path = Path(file)
        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

        with scenario_path.open("r", encoding="utf-8") as fh:
            try:
                payload = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in scenario file {scenario_path}: {exc}") from exc

        env_data = payload.get("environment")
        if not env_data:
            raise ValueError("Scenario file missing 'environment' section")

        inflow = _parse_timeseries(env_data.get("inflow_series", []))
        outflow = _parse_timeseries(env_data.get("outflow_series", []))

        env = Environment(
            volume=_require(env_data, "volume"),
            area=_require(env_data, "area"),
            depth_mean=_require(env_data, "depth_mean"),
            depth_max=_require(env_data, "depth_max"),
            inflow_series=inflow,
            outflow_series=outflow,
        )

        states_payload = payload.get("state_variables", [])
        if not isinstance(states_payload, list):
            raise ValueError("'state_variables' section must be a list")

        state_vars: list[StateVariable] = []
        for raw in states_payload:
            sv_type = raw.get("type")
            if sv_type == "nutrient":
                state_vars.append(
                    Nutrient(
                        name=_require(raw, "name"),
                        value=_require(raw, "value"),
                        units=_require(raw, "units"),
                        form=_require(raw, "form"),
                    )
                )
            else:
                raise ValueError(f"Unsupported state variable type: {sv_type!r}")

        return env, state_vars

    @staticmethod
    def load_forcing(file: str) -> dict:
        """Placeholder hook for loading external forcing data for future stages."""
        # Placeholder for later: inflow/load time series, meteorology, etc.
        return {}

    @staticmethod
    def save_output(results, file: str) -> None:
        """Persist simulation results to disk using a minimal CSV-like layout.

        Parameters
        ----------
        results:
            Sequence of ``(datetime, {state_name: value})`` tuples produced by
            :meth:`aquatox.core.Simulation.output_results`.
        file:
            Destination file that will be overwritten with CSV content.
        """
        # Minimal CSV-like writer
        if not results:
            return
        import csv
        times, first = results[0]
        names = sorted(first.keys())
        with open(file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time"] + names)
            for t, snapshot in results:
                w.writerow([t.isoformat()] + [snapshot.get(n, "") for n in names])

class Utils:
    """Utility functions mirroring helper slots from the AQUATOX UML diagrams.

    Stage-1 does not yet require the numerical helpers outlined by the UML, but
    providing explicit placeholders clarifies where the future logic will live.
    """
    @staticmethod
    def interpolate_series(series, t):
        """Return the raw series value, deferring real interpolation to later."""
        # Stage-1: exact lookup (same as Environment); real interpolation later
        return series.get(t, 0.0)

    @staticmethod
    def calc_light_penetration():
        """Return a constant attenuation factor until optical model is wired in."""
        # Placeholder; implemented in later stages
        return 1.0
