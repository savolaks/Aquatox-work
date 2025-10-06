# tests/test_stage1.py
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from aquatox.core import Simulation, ODESolver, Environment
from aquatox.state import StateVariable, Nutrient, Biota
from aquatox.io_utils import ScenarioIO

# ---- Helpers ----
class ConstantRateVar(StateVariable):
    def rate(self, t, dt, env, state_vars):
        return self._c

    def __init__(self, name, value, units, c):
        super().__init__(name=name, value=value, units=units)
        self._c = c

def _mk_env_with_flows(v0=1000.0, inflow=10.0, outflow=5.0, days=2):
    t0 = datetime(1992,1,1)
    inflow_series = {t0 + timedelta(days=i): inflow for i in range(days+1)}
    outflow_series = {t0 + timedelta(days=i): outflow for i in range(days+1)}
    return Environment(
        volume=v0, area=1000.0, depth_mean=5.4, depth_max=25.0,
        inflow_series=inflow_series, outflow_series=outflow_series
    ), t0

# ---- Tests ----
def test_euler_integrator_constant_rate_step():
    env, t0 = _mk_env_with_flows()
    x = ConstantRateVar(name="X", value=0.0, units="arb", c=5.0)  # dX/dt = 5
    sim = Simulation(env=env, state_vars=[x], solver=ODESolver(method="Euler"))
    sim.solver.integrate(sim.state_vars, env, t0, dt_days=1.0)
    assert x.value == pytest.approx(5.0)

def test_environment_water_balance_updates_volume():
    env, t0 = _mk_env_with_flows(v0=1000.0, inflow=10.0, outflow=5.0, days=1)
    x = ConstantRateVar(name="X", value=0.0, units="arb", c=0.0)
    sim = Simulation(env=env, state_vars=[x], solver=ODESolver(method="Euler"))
    sim.run(time_end=t0 + timedelta(days=1), dt_days=1.0)
    # Volume = 1000 + (10-5)*1day = 1005
    assert sim.env.volume == pytest.approx(1005.0)

def test_scenarioio_minimal_load_and_run_stable():
    scenario_path = Path(__file__).parent / "data" / "pyhajarvi_stub.json"
    sim = Simulation.load_scenario(str(scenario_path))
    # run two days
    end = min(sim.env.inflow_series.keys()) + timedelta(days=2)
    sim.run(time_end=end, dt_days=1.0)
    out = sim.output_results()
    assert len(out) >= 2
    # Nitrate is inert in Stage-1 -> unchanged
    nitrates = [frame["Nitrate"] for _, frame in out]
    assert all(v == pytest.approx(0.4) for v in nitrates)

def test_biota_growth_minus_mortality():
    env, t0 = _mk_env_with_flows()
    b = Biota(name="TestBiota", value=1.0, units="mg/L", biomass=1.0, max_growth=0.2, mortality_rate=0.1)
    sim = Simulation(env=env, state_vars=[b], solver=ODESolver(method="Euler"))
    sim.solver.integrate(sim.state_vars, env, t0, dt_days=1.0)
    # Net rate = (0.2 - 0.1)*1.0 = 0.1 -> value should be 1.1
    assert b.value == pytest.approx(1.1, rel=1e-6)
