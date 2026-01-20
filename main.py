import argparse
from datetime import datetime
from pathlib import Path

from aquatox.core import simulate_water_volume, Simulation, ODESolver
from aquatox.excel_utils import write_excel
from aquatox.io_utils import ScenarioIO
from aquatox.state import Biota

def _parse_date(raw: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError("Use dd/mm/yyyy or d.m.yyyy for dates.")


def _build_matrix_table(names, matrix):
    header = ["predator \\ prey"] + list(names)
    rows = [header]
    for pred, row in zip(names, matrix):
        rows.append([pred] + ["" if value is None else value for value in row])
    return rows


def _normalize_matrix(matrix):
    normalized = []
    for row in matrix:
        positives = [value for value in row if isinstance(value, (int, float)) and value > 0]
        total = sum(positives)
        if total > 0:
            normalized.append(
                [
                    None
                    if value is None
                    else (value / total if isinstance(value, (int, float)) and value > 0 else 0.0)
                    for value in row
                ]
            )
        else:
            normalized.append([None if value is None else 0.0 for value in row])
    return normalized


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
    parser.add_argument(
        "--temp-series-output",
        help="Optional CSV output path for epilimnion/hypolimnion temperature series.",
    )
    parser.add_argument(
        "--temperature-output",
        help="Optional CSV output path for simulated temperature output.",
    )
    parser.add_argument(
        "--food-web",
        help="Optional interspecies CSV (.cn). Defaults to AQ_Species_Models.cn in cwd.",
    )
    parser.add_argument(
        "--foodweb-output",
        help="Optional Excel output path (.xml or .xlsx) for 2D food web matrices.",
    )
    args = parser.parse_args()

    print(f"Starting scenario load from file: {args.input}")
    env, state_vars = ScenarioIO.load_initial_conditions(
        args.input,
        food_web_path=args.food_web,
    )
    print("Environment values initialized:")
    print(f"  volume = {env.volume}")
    print(f"  area = {env.area}")
    print(f"  depth_mean = {env.depth_mean}")
    print(f"  depth_max = {env.depth_max}")
    print(f"  inflow_series entries = {len(env.inflow_series)}")
    print(f"  outflow_series entries = {len(env.outflow_series)}")
    print(f"  temp_epi_series entries = {len(env.temp_epi_series)}")
    print(f"  temp_hypo_series entries = {len(env.temp_hypo_series)}")
    print(f"  temp_forcing_mode = {env.temp_forcing_mode}")
    print(f"  food_web loaded = {env.food_web is not None}")

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
        if args.temperature_output is None:
            out_path = Path(args.output)
            args.temperature_output = str(out_path.with_name(out_path.stem + "_temperature.csv"))

    if args.temp_series_output:
        ScenarioIO.save_temperature_series(
            env.temp_epi_series,
            env.temp_hypo_series,
            args.temp_series_output,
        )
        print(f"Wrote temperature series to: {args.temp_series_output}")

    if args.temperature_output:
        sim = Simulation(env=env, state_vars=state_vars, solver=ODESolver(method="Euler"))
        sim.run(time_end=end, dt_days=args.dt)
        ScenarioIO.save_output(sim.output_results(), args.temperature_output)
        print(f"Wrote temperature output to: {args.temperature_output}")

    if args.foodweb_output:
        if env.food_web is None:
            print("Food web not available; skipping food web export.")
        else:
            organisms = [sv for sv in state_vars if isinstance(sv, Biota)]
            names, preferences, egestion = env.food_web.build_foodweb_matrices(organisms)
            if not names:
                print("No biota initialized; skipping food web export.")
            else:
                pref_table_raw = _build_matrix_table(names, preferences)
                pref_table_norm = _build_matrix_table(names, _normalize_matrix(preferences))
                egestion_table = _build_matrix_table(names, egestion)
                write_excel(
                    args.foodweb_output,
                    {
                        "Preferences (Raw)": pref_table_raw,
                        "Preferences (Normalized)": pref_table_norm,
                        "Egestion Coefficients": egestion_table,
                    },
                )
                print(f"Wrote food web Excel XML to: {args.foodweb_output}")

if __name__ == "__main__":
    main()
