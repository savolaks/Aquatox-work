from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from aquatox.core import Simulation


def _infer_start_time(sim: Simulation) -> datetime:
    """Return the earliest timestamp from inflow/outflow data to use as start.

    The helper mirrors the logic inside :meth:`aquatox.core.Simulation.run` but
    raises an explicit error when neither inflow nor outflow series are
    available so that the CLI can fail fast with a human readable message.
    """
    if sim.env.inflow_series:
        return min(sim.env.inflow_series.keys())
    if sim.env.outflow_series:
        return min(sim.env.outflow_series.keys())
    raise ValueError(
        "Scenario needs at least one inflow/outflow timestamp; provide a file "
        "with time series data or extend the driver to accept a custom start."
    )


def parse_args() -> argparse.Namespace:
    """Configure the command line interface and parse the provided arguments.

    Returns
    -------
    argparse.Namespace
        Populated namespace containing the scenario path, simulation duration
        and timestep length supplied by the caller.
    """
    parser = argparse.ArgumentParser(description="Run an AQUATOX Stage-1 scenario")
    parser.add_argument(
        "--scenario",
        "-s",
        type=Path,
        default=Path("tests/data/pyhajarvi_stub.json"),
        help="Path to a JSON scenario file (defaults to the bundled Pyhäjärvi stub).",
    )
    parser.add_argument(
        "--days",
        type=float,
        default=2.0,
        help="Simulation length in days (will be added to the inferred start date).",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=1.0,
        help="Timestep in days for the Euler solver.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry-point that loads the scenario file and runs the Stage-1 simulation.

    The function keeps side effects (printing results) local so that it remains
    trivial to wrap the driver in automated tests or higher level orchestration
    scripts later in the project.
    """
    args = parse_args()
    scenario_path = args.scenario.expanduser()
    sim = Simulation.load_scenario(str(scenario_path))

    start = _infer_start_time(sim)
    time_end = start + timedelta(days=args.days)
    sim.run(time_end=time_end, dt_days=args.dt)

    print(f"Scenario: {scenario_path}")
    print(f"Duration: {args.days} days with dt={args.dt}")
    print(f"Final volume (m^3): {sim.env.volume:.3f}")
    print("Outputs (time, states):")
    for t, snapshot in sim.output_results():
        date = t.date().isoformat()
        formatted_states = ", ".join(f"{name}={value:.4g}" for name, value in snapshot.items())
        print(f"  {date}: {formatted_states}")


if __name__ == "__main__":
    main()
