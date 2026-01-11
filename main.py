from datetime import timedelta
from aquatox.core import Simulation, ODESolver
from aquatox.io_utils import ScenarioIO

def main():
    file_path = "LakePyhajarviFinland.txt"
    print(f"Starting scenario load from file: {file_path}")
    env, state_vars = ScenarioIO.load_initial_conditions(file_path)
    print("Environment values initialized:")
    print(f"  volume = {env.volume}")
    print(f"  area = {env.area}")
    print(f"  depth_mean = {env.depth_mean}")
    print(f"  depth_max = {env.depth_max}")
    print(f"  inflow_series entries = {len(env.inflow_series)}")
    print(f"  outflow_series entries = {len(env.outflow_series)}")
    print("State variables initialized:")
    for sv in state_vars:
        print(f"  {sv.__class__.__name__}: {sv.name} = {sv.value} {sv.units}")

    sim = Simulation(env=env, state_vars=state_vars, solver=ODESolver(method="Euler"))
    start = min(sim.env.inflow_series.keys())
    end = start + timedelta(days=10)
    sim.run(time_end=end, dt_days=1.0)

    print("Final volume (m^3):", sim.env.volume)
    print("Outputs (time, states):")
    for t, snapshot in sim.output_results():
        print(t.date(), snapshot)

if __name__ == "__main__":
    main()
