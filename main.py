import argparse
from datetime import datetime
from pathlib import Path

from aquatox.core import simulate_water_volume
from aquatox.excel_utils import write_excel_xml
from aquatox.io_utils import ScenarioIO
from aquatox.state import Biota

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
    parser.add_argument(
        "--food-web",
        help="Optional interspecies CSV (.cn). Defaults to AQ_Species_Models.cn in cwd.",
    )
    parser.add_argument(
        "--foodweb-output",
        help="Optional Excel XML output path for 2D food web matrices.",
    )
    parser.add_argument(
        "--debug-foodweb",
        action="store_true",
        help="Print food web matching diagnostics.",
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

    if args.foodweb_output:
        if env.food_web is None:
            print("Food web not available; skipping food web export.")
        else:
            organisms = [sv for sv in state_vars if isinstance(sv, Biota)]
            names, preferences, egestion = env.food_web.build_foodweb_matrices(organisms)
            if args.debug_foodweb:
                _print_foodweb_debug(env.food_web, organisms)
            if not names:
                print("No biota initialized; skipping food web export.")
            else:
                pref_table = _build_matrix_table(names, preferences)
                egestion_table = _build_matrix_table(names, egestion)
                write_excel_xml(
                    args.foodweb_output,
                    {
                        "Preferences": pref_table,
                        "Egestion Coefficients": egestion_table,
                    },
                )
                print(f"Wrote food web Excel XML to: {args.foodweb_output}")


def _build_matrix_table(names, matrix):
    header = ["predator \\ prey"] + list(names)
    rows = [header]
    for pred, row in zip(names, matrix):
        rows.append([pred] + ["" if value is None else value for value in row])
    return rows


def _print_foodweb_debug(food_web, organisms):
    import re

    def norm(name: str) -> str:
        lowered = name.strip().lower()
        lowered = re.sub(r"[()]", "", lowered)
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    organism_names = [sv.name for sv in organisms]
    organism_norms = {norm(name): name for name in organism_names}
    predator_raw = list(food_web._predator_index.keys())
    predator_norms = {norm(name): name for name in predator_raw}

    matched_predators = []
    unmatched_predators = []
    for raw in predator_raw:
        if raw in organism_names or norm(raw) in organism_norms:
            matched_predators.append(raw)
        else:
            unmatched_predators.append(raw)

    print("Food web debug:")
    print(f"  biota count = {len(organism_names)}")
    print(f"  predator entries = {len(predator_raw)}")
    print(f"  predators matched = {len(matched_predators)}")
    print(f"  predators unmatched = {len(unmatched_predators)}")
    sample_missing = unmatched_predators[:10]
    if sample_missing:
        print("  sample unmatched predators:")
        for name in sample_missing:
            print(f"    - {name}")

if __name__ == "__main__":
    main()
