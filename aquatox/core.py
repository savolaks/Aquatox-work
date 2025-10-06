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
    """Container for the lake geometry and external hydrological forcing.

    Attributes
    ----------
    volume:
        Instantaneous lake volume in cubic metres.
    area:
        Surface area of the lake in square metres.
    depth_mean / depth_max:
        Representative depth metrics that will later feed sediment exchange
        calculations.
    inflow_series / outflow_series:
        Daily volumetric boundary conditions indexed by timestamp.  For the
        Stage-1 prototype the series are assumed to contain exact timestamps
        that can be looked up without interpolation.
    """

    volume: float                 # m^3     <<initial lake volume>>
    area: float                   # m^2     <<surface area>>
    depth_mean: float             # m
    depth_max: float              # m
    inflow_series: Dict[Date, float]   # m^3/day
    outflow_series: Dict[Date, float]  # m^3/day

    def get_inflow(self, t: Date) -> float:
        """Return the inflow boundary condition for the requested timestep.

        Parameters
        ----------
        t:
            Timestamp associated with the integration step.
        """
        return self._get_series_value(self.inflow_series, t)

    def get_outflow(self, t: Date) -> float:
        """Return the outflow boundary condition for the requested timestep."""
        return self._get_series_value(self.outflow_series, t)

    @staticmethod
    def _get_series_value(series: Dict[Date, float], t: Date) -> float:
        """Stage-1 helper that fetches exact timestamp matches from a series.

        Later stages will need temporal interpolation; recording the logic here
        keeps the refactor localised to this method.
        """
        # exact timestamp match; Stage-1 simple version
        return series.get(t, 0.0)

# ---------------------------
# StateVariable hierarchy (forward ref; real classes in state.py)
# ---------------------------
class StateVariable:
    """Abstract base for all mass/energy compartments simulated by AQUATOX."""
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
    """Numerical integrator responsible for advancing state variables in time.

    Only the classic forward Euler scheme is wired for Stage-1 to keep the
    control flow transparent while the biochemical modules are stubbed out.
    """
    method: str = "Euler"  # <<"Euler","RK4", etc.>>

    def integrate(self, state_vars: List[StateVariable], env: Environment, t: Date, dt_days: float) -> None:
        """Advance each state variable by a single explicit integration step.

        Parameters
        ----------
        state_vars:
            Sequence of state variable objects that expose a ``rate`` method.
        env:
            Shared :class:`Environment` instance used by state variables when
            computing their dynamics.
        t:
            Timestamp at which the derivative is evaluated.
        dt_days:
            Integration step expressed in days.  Euler updates are executed
            in-place to mirror the dataflow in the original AQUATOX UML
            diagrams.
        """
        # Stage-1: Euler explicit.
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
    """Coordinate the coupled integration of the environment and state variables.

    The class glues together the environment, biological/chemical state
    variables, and the numerical solver.  Its role is intentionally lightweight
    so that later stages can extend it with more sophisticated output handling
    and scenario management without rewriting the surrounding tooling.
    """
    env: Environment
    state_vars: List[StateVariable]
    solver: ODESolver
    _outputs: List[Tuple[Date, Dict[str, float]]] = field(default_factory=list)

    @classmethod
    def load_scenario(cls, file_path: str) -> "Simulation":
        """Instantiate a :class:`Simulation` from the JSON scenario on disk."""
        # Delegated in io_utils.ScenarioIO; left here to match UML signature
        from .io_utils import ScenarioIO
        env, svs = ScenarioIO.load_initial_conditions(file_path)
        solver = ODESolver(method="Euler")
        return cls(env=env, state_vars=svs, solver=solver)

    def run(self, time_end: Date, dt_days: float) -> None:
        """Advance the model from its inferred start time until ``time_end``.

        Results are accumulated into ``_outputs`` to provide a lightweight audit
        trail for the integration and to feed the command line summary printer.
        """
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
            # 1) Integrate biological/chemical compartments to obtain updated
            #    state values for this timestep.
            self.solver.integrate(self.state_vars, self.env, t, dt_days)

            # 2) Update hydrology (simple water balance: m^3).  This keeps the
            #    lake volume consistent with external inflows/outflows while we
            #    defer sediment exchange and evaporation to later stages.
            inflow = self.env.get_inflow(t)    # m^3/day
            outflow = self.env.get_outflow(t)  # m^3/day
            self.env.volume += (inflow - outflow) * dt_days

            # 3) Record outputs in case the caller wants to inspect trajectories
            #    or persist them to disk.
            snapshot = {sv.name: sv.value for sv in self.state_vars}
            self._outputs.append((t, snapshot))

            # 4) Advance time using the configured step size.
            t = t + timedelta(days=dt_days)

    def output_results(self) -> List[Tuple[Date, Dict[str, float]]]:
        """Return recorded state snapshots gathered during ``run``."""
        return list(self._outputs)
