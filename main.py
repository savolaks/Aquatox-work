import argparse
from datetime import datetime
from pathlib import Path

from aquatox.core import simulate_water_volume
from aquatox.io_utils import ScenarioIO

def _parse_date(raw: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError("Use dd/mm/yyyy or d.m.yyyy for dates.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate AQUATOX water volume using inflow/outflow time series."
    )
    parser.add_argument(
        "-i",
        "--input",
        default="Lake Pyhajarvi Finland_regression.txt",
        help="Scenario input file.",
    )
    parser.add_argument("--start", help="Start date (dd/mm/yyyy or d.m.yyyy).")
    parser.add_argument("--end", help="End date (dd/mm/yyyy or d.m.yyyy).")
    parser.add_argument("--dt", type=float, default=1.0, help="Time step in days.")
    parser.add_argument("-o", "--output", help="Optional CSV output path.")
    parser.add_argument(
        "--series-output",
        help="Optional CSV output path for inflow/outflow time series.",
    )
    args = parser.parse_args()

    print(f"Starting scenario load from file: {args.input}")
    env, _ = ScenarioIO.load_initial_conditions(args.input)
    print("Environment values initialized:")
    print(f"  volume = {env.volume}")
    print(f"  area = {env.area}")
    print(f"  depth_mean = {env.depth_mean}")
    print(f"  depth_max = {env.depth_max}")
    print(f"  inflow_series entries = {len(env.inflow_series)}")
    print(f"  outflow_series entries = {len(env.outflow_series)}")

    series_keys = set(env.inflow_series.keys()) | set(env.outflow_series.keys())
    if not series_keys:
        print("No inflow/outflow series found; cannot run waterflow simulation.")
        return

    start = _parse_date(args.start) if args.start else min(series_keys)
    end = _parse_date(args.end) if args.end else max(series_keys)
    if start > end:
        raise ValueError("Start date must be on or before end date.")

    results = simulate_water_volume(env, time_start=start, time_end=end, dt_days=args.dt)
    print("Final volume (m^3):", env.volume)
    print(f"Simulated steps: {len(results)}")

    if args.output:
        ScenarioIO.save_waterflow_output(results, args.output)
        print(f"Wrote CSV output to: {args.output}")
        series_output = args.series_output
        if series_output is None:
            out_path = Path(args.output)
            series_output = str(out_path.with_name(out_path.stem + "_series.csv"))
        ScenarioIO.save_inflow_outflow_series(
            env.inflow_series,
            env.outflow_series,
            series_output,
        )
        print(f"Wrote inflow/outflow series to: {series_output}")

if __name__ == "__main__":
    main()
