# aquatox/io_utils.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from .core import Environment
from .state import StateVariable, Nutrient

class ScenarioIO:
    @staticmethod
    def load_initial_conditions(file: str) -> tuple[Environment, list[StateVariable]]:
        """Stage-1 stub: returns a tiny synthetic scenario.
        Later we'll parse real Pyhäjärvi files; this keeps tests deterministic.
        """
        # A two-day time axis for flows
        t0 = datetime(1992, 1, 1)
        inflow_series = {t0 + timedelta(days=i): 10.0 for i in range(10)}   # m^3/day
        outflow_series = {t0 + timedelta(days=i): 10.0 for i in range(10)}   # m^3/day

        env = Environment(
            volume=1_000.0,   # m^3
            area=1_000.0,     # m^2
            depth_mean=5.4,
            depth_max=25.0,
            inflow_series=inflow_series,
            outflow_series=outflow_series
        )

        # One inert nutrient to verify solver loop (units mg/L as placeholder)
        nitrate = Nutrient(name="Nitrate", value=0.4, units="mg/L", form="NO3")

        return env, [nitrate]

    @staticmethod
    def load_forcing(file: str) -> dict:
        # Placeholder for later: inflow/load time series, meteorology, etc.
        return {}

    @staticmethod
    def save_output(results, file: str) -> None:
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
    @staticmethod
    def interpolate_series(series, t):
        # Stage-1: exact lookup (same as Environment); real interpolation later
        return series.get(t, 0.0)

    @staticmethod
    def calc_light_penetration():
        # Placeholder; implemented in later stages
        return 1.0
