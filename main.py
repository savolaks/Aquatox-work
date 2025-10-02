from datetime import timedelta
from aquatox.core import Simulation

def main():
    sim = Simulation.load_scenario("dummy-scenario")
    start = min(sim.env.inflow_series.keys())
    end = start + timedelta(days=10)
    sim.run(time_end=end, dt_days=1.0)

    print("Final volume (m^3):", sim.env.volume)
    print("Outputs (time, states):")
    for t, snapshot in sim.output_results():
        print(t.date(), snapshot)

if __name__ == "__main__":
    main()