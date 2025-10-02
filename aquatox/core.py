# aquatox/core.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from .typing_ext import Date

# ---------------------------
# Environment (per UML)
# ---------------------------
@dataclass
class Environment:
    volume: float                 # m^3     <<initial lake volume>>
    area: float                   # m^2     <<surface area>>
    depth_mean: float             # m
    depth_max: float              # m
    inflow_series: Dict[Date, float]   # m^3/day
    outflow_series: Dict[Date, float]  # m^3/day

    def get_inflow(self, t: Date) -> float:
        return self._get_series_value(self.inflow_series, t)

    def get_outflow(self, t: Date) -> float:
        return self._get_series_value(self.outflow_series, t)

    @staticmethod
    def _get_series_value(series: Dict[Date, float], t: Date) -> float:
        # exact timestamp match; Stage-1 simple version
        return series.get(t, 0.0)

# ---------------------------
# StateVariable hierarchy (forward ref; real classes in state.py)
# ---------------------------
class StateVariable:
    name: str
    value: float
    units: str
    def rate(self, t: Date, dt: float, env: "Environment", state_vars: List["StateVariable"]) -> float:
        raise NotImplementedError

# ---------------------------
# ODESolver (per UML)
# ---------------------------
@dataclass
class ODESolver:
    method: str = "Euler"  # <<"Euler","RK4", etc.>>

    def integrate(self, state_vars: List[StateVariable], env: Environment, t: Date, dt_days: float) -> None:
        """Update all state_vars in place using the chosen method.
        Stage-1: Euler explicit.
        """
        if self.method != "Euler":
            raise NotImplementedError("Only Euler is implemented in Stage-1.")

        # Compute all rates with the current state (avoid in-step side effects)
        rates = [sv.rate(t, dt_days, env, state_vars) for sv in state_vars]

        # Euler step: x_{n+1} = x_n + dt * f(x_n, t)
        for sv, r in zip(state_vars, rates):
            sv.value += dt_days * r

# ---------------------------
# Simulation (per UML)
# ---------------------------
@dataclass
class Simulation:
    env: Environment
    state_vars: List[StateVariable]
    solver: ODESolver
    _outputs: List[Tuple[Date, Dict[str, float]]] = field(default_factory=list)

    @classmethod
    def load_scenario(cls, file_path: str) -> "Simulation":
        # Delegated in io_utils.ScenarioIO; left here to match UML signature
        from .io_utils import ScenarioIO
        env, svs = ScenarioIO.load_initial_conditions(file_path)
        solver = ODESolver(method="Euler")
        return cls(env=env, state_vars=svs, solver=solver)

    def run(self, time_end: Date, dt_days: float) -> None:
        """Main loop: update env volume via flows; integrate states."""
        if not self.state_vars:
            return
        # Decide start time from earliest inflow key or now if absent
        if self.env.inflow_series:
            t = min(self.env.inflow_series.keys())
        elif self.env.outflow_series:
            t = min(self.env.outflow_series.keys())
        else:
            t = datetime.utcnow()

        while t < time_end:
            # 1) integrate biological/chemical compartments
            self.solver.integrate(self.state_vars, self.env, t, dt_days)

            # 2) update hydrology (simple water balance: m^3)
            inflow = self.env.get_inflow(t)    # m^3/day
            outflow = self.env.get_outflow(t)  # m^3/day
            self.env.volume += (inflow - outflow) * dt_days

            # 3) record outputs
            snapshot = {sv.name: sv.value for sv in self.state_vars}
            self._outputs.append((t, snapshot))

            # 4) advance time
            t = t + timedelta(days=dt_days)

    def output_results(self) -> List[Tuple[Date, Dict[str, float]]]:
        return list(self._outputs)
