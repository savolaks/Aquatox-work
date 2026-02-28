import argparse
from datetime import datetime, timedelta
from pathlib import Path

from aquatox.core import Simulation, ODESolver
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
        description="Simulate AQUATOX and export either all variables to CSV or the food web to Excel."
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
    parser.add_argument(
        "--food-web",
        help="Optional interspecies CSV (.cn). Defaults to AQ_Species_Models.cn in cwd.",
    )
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument(
        "--all-series-csv",
        help="CSV output path for all simulation variables.",
    )
    output_group.add_argument(
        "--foodweb-excel",
        help="Excel output path (.xml or .xlsx) for 2D food web matrices.",
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
    print(f"  wind_series entries = {len(env.wind_series)}")
    print(f"  wind_forcing_mode = {env.wind_forcing_mode}")
    print(f"  light_series entries = {len(env.light_series)}")
    print(f"  light_forcing_mode = {env.light_forcing_mode}")
    print(f"  ph_series entries = {len(env.ph_series)}")
    print(f"  ph_forcing_mode = {env.ph_forcing_mode}")
    print(f"  tss_series entries = {len(env.tss_series)}")
    print(f"  tss_forcing_mode = {env.tss_forcing_mode}")
    print(f"  inorganic_solids_mode = {env.inorganic_solids_mode}")
    print(f"  food_web loaded = {env.food_web is not None}")

    series_keys = set(env.inflow_series.keys()) | set(env.outflow_series.keys())
    if not series_keys:
        print("No inflow/outflow series found; cannot run waterflow simulation.")
        return

    start = _parse_date(args.start) if args.start else min(series_keys)
    end = _parse_date(args.end) if args.end else max(series_keys)
    if start > end:
        raise ValueError("Start date must be on or before end date.")

    simulation = Simulation(env=env, state_vars=state_vars, solver=ODESolver(method="Euler"))
    simulation.run(time_end=end, dt_days=args.dt, time_start=start)
    results = simulation.output_results()
    print("Final volume (m^3):", env.volume)
    print(f"Simulated steps: {len(results)}")

    confirm = input("Export outputs now? [y/N] ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Export skipped by user.")
        return

    if args.all_series_csv:
        rows = []
        for t, snapshot in results:
            temp_epi = None
            temp_hypo = None
            if env.temp_epi_series:
                temp_epi = env._get_series_value(env.temp_epi_series, t)
                if env.temp_hypo_series:
                    temp_hypo = env._get_series_value(env.temp_hypo_series, t)
                else:
                    temp_hypo = temp_epi
            elif env.temp_forcing_mode in ("series", "series_interpolate", "mean_range", "constant"):
                epi_value, hypo_value, _ = env.get_temperature_pair(t)
                temp_epi = epi_value
                temp_hypo = hypo_value
            ph_value = (
                env._get_series_value(env.ph_series, t) if env.ph_series else env.get_ph(t)
            )
            rows.append(
                (
                    t,
                    {
                        "volume_m3": snapshot.get("volume_m3", env.volume),
                        "inflow_m3_per_day": snapshot.get("inflow_m3_per_day"),
                        "outflow_m3_per_day": snapshot.get("outflow_m3_per_day"),
                        "temp_epi_degC": temp_epi,
                        "temp_hypo_degC": temp_hypo,
                        "wind_m_s": env.get_wind(t),
                        "light_ly_d": env.get_light(t),
                        "ph": ph_value,
                        "tss_mg_l": env.get_tss(t),
                    },
                )
            )
        ScenarioIO.save_all_series(rows, args.all_series_csv)
        print(f"Wrote all series output to: {args.all_series_csv}")

    if args.foodweb_excel:
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
                    args.foodweb_excel,
                    {
                        "Preferences (Raw)": pref_table_raw,
                        "Preferences (Normalized)": pref_table_norm,
                        "Egestion Coefficients": egestion_table,
                    },
                )
                print(f"Wrote food web Excel XML to: {args.foodweb_excel}")

if __name__ == "__main__":
    main()
