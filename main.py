import argparse
from datetime import datetime, timedelta
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
        "--wind-output",
        help="Optional CSV output path for simulated wind output.",
    )
    parser.add_argument(
        "--light-output",
        help="Optional CSV output path for simulated light output.",
    )
    parser.add_argument(
        "--ph-output",
        help="Optional CSV output path for simulated pH output.",
    )
    parser.add_argument(
        "--tss-output",
        help="Optional CSV output path for simulated TSS output.",
    )
    parser.add_argument(
        "--all-series-output",
        help="Optional CSV output path for combined forcing series output.",
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

    if args.wind_output:
        wind_series = {}
        t = start
        while t < end:
            wind_value = env.get_wind(t)
            if wind_value is not None:
                wind_series[t] = wind_value
            t = t + timedelta(days=args.dt)
        ScenarioIO.save_wind_series(wind_series, args.wind_output)
        print(f"Wrote wind output to: {args.wind_output}")

    if args.light_output:
        light_series = {}
        t = start
        while t < end:
            light_value = env.get_light(t)
            if light_value is not None:
                light_series[t] = light_value
            t = t + timedelta(days=args.dt)
        ScenarioIO.save_light_series(light_series, args.light_output)
        print(f"Wrote light output to: {args.light_output}")

    if args.ph_output:
        ph_series = {}
        t = start
        while t < end:
            ph_value = env.get_ph(t)
            if ph_value is not None:
                ph_series[t] = ph_value
            t = t + timedelta(days=args.dt)
        ScenarioIO.save_ph_series(ph_series, args.ph_output)
        print(f"Wrote pH output to: {args.ph_output}")

    if args.tss_output:
        tss_series = {}
        t = start
        while t < end:
            tss_value = env.get_tss(t)
            if tss_value is not None:
                tss_series[t] = tss_value
            t = t + timedelta(days=args.dt)
        ScenarioIO.save_tss_series(tss_series, args.tss_output)
        print(f"Wrote TSS output to: {args.tss_output}")

    if args.all_series_output:
        rows = []
        volume = env.volume
        t = start
        while t < end:
            inflow = env.get_inflow(t)
            outflow = env.get_outflow(t)
            volume += (inflow - outflow) * args.dt
            temp_epi = None
            temp_hypo = None
            if env.temp_forcing_mode in ("series", "series_interpolate", "mean_range", "constant"):
                epi_value, hypo_value, _ = env.get_temperature_pair(t)
                temp_epi = epi_value
                temp_hypo = hypo_value
            rows.append(
                (
                    t,
                    {
                        "volume_m3": volume,
                        "inflow_m3_per_day": inflow,
                        "outflow_m3_per_day": outflow,
                        "temp_epi_degC": temp_epi,
                        "temp_hypo_degC": temp_hypo,
                        "wind_m_s": env.get_wind(t),
                        "light_ly_d": env.get_light(t),
                        "ph": env.get_ph(t),
                        "tss_mg_l": env.get_tss(t),
                    },
                )
            )
            t = t + timedelta(days=args.dt)
        ScenarioIO.save_all_series(rows, args.all_series_output)
        print(f"Wrote all series output to: {args.all_series_output}")

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
