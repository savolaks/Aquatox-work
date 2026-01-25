# aquatox/io_utils.py
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
from typing import Dict

from .core import Environment
from .state import StateVariable, Nutrient, Detritus, Plant, Animal, Biota

class ScenarioIO:
    @staticmethod
    def load_initial_conditions(
        file: str,
        food_web_path: str | None = None,
    ) -> tuple[Environment, list[StateVariable]]:
        """Load a scenario file, prompting for any missing data."""
        path = Path(file)
        text = ""
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")

        env = ScenarioIO._build_environment(text)
        state_vars = ScenarioIO._parse_state_variables(text)
        if not state_vars:
            state_vars = ScenarioIO._prompt_state_variables()
        if env.inorganic_solids_mode == "tss" and env.tss_initial is not None:
            ScenarioIO._apply_tss_initial(state_vars, env.tss_initial)

        env.chemicals = ScenarioIO._parse_chemicals(text)
        env.chemical_states = ScenarioIO._parse_chemical_states(text, env.chemicals)
        env.inflow_loadings = ScenarioIO._parse_inflow_loadings(text)
        env.direct_precip_loadings = ScenarioIO._parse_direct_precip_loadings(text)
        env.point_source_loadings = ScenarioIO._parse_point_source_loadings(text)
        env.nonpoint_source_loadings = ScenarioIO._parse_nonpoint_source_loadings(text)

        food_web = ScenarioIO._parse_foodweb_from_scenario(text)
        if food_web is None:
            resolved_food_web = None
            if food_web_path:
                resolved_food_web = Path(food_web_path)
            else:
                default_path = Path.cwd() / "AQ_Species_Models.cn"
                if default_path.exists():
                    resolved_food_web = default_path

            if resolved_food_web and resolved_food_web.exists():
                from .foodweb import FoodWeb

                food_web = FoodWeb.from_interspecies_csv(str(resolved_food_web))

        env.food_web = food_web
        return env, state_vars

    @staticmethod
    def _build_environment(text: str) -> Environment:
        volume = ScenarioIO._find_float(text, r'"StaticVolume":\s*([-\d.E+]+)')
        area = ScenarioIO._find_float(text, r'"SurfArea":\s*([-\d.E+]+)')
        depth_mean = ScenarioIO._find_float(text, r'"ICZMean":\s*([-\d.E+]+)')
        depth_max = ScenarioIO._find_float(text, r'"ZMax":\s*([-\d.E+]+)')
        inflow_series = ScenarioIO._parse_inflow_series(text)
        outflow_series = ScenarioIO._parse_outflow_series(text)
        temp_epi_series, temp_hypo_series = ScenarioIO._parse_temperature_series(text)
        temp_epi_const, temp_hypo_const = ScenarioIO._parse_temperature_constants(text)
        temp_epi_mean, temp_epi_range, temp_hypo_mean, temp_hypo_range = (
            ScenarioIO._parse_temperature_mean_range(text)
        )
        wind_series = ScenarioIO._parse_wind_series(text)
        wind_constant = ScenarioIO._parse_wind_constant(text)
        wind_mean = ScenarioIO._parse_wind_mean(text)
        wind_use_constant = ScenarioIO._parse_wind_use_constant(text)
        light_series = ScenarioIO._parse_light_series(text)
        light_constant = ScenarioIO._parse_light_constant(text)
        light_mean, light_range = ScenarioIO._parse_light_mean_range(text)
        light_use_constant = ScenarioIO._parse_light_use_constant(text)
        ph_series = ScenarioIO._parse_ph_series(text)
        ph_constant = ScenarioIO._parse_ph_constant(text)
        ph_use_constant = ScenarioIO._parse_ph_use_constant(text)
        tss_series = ScenarioIO._parse_tss_series(text)
        tss_constant = ScenarioIO._parse_tss_constant(text)
        tss_initial = ScenarioIO._parse_tss_initial(text)
        tss_use_constant = ScenarioIO._parse_tss_use_constant(text)
        temp_forcing_mode = ScenarioIO._choose_temperature_mode(
            temp_epi_series,
            temp_hypo_series,
            temp_epi_mean,
            temp_epi_range,
            temp_hypo_mean,
            temp_hypo_range,
        )
        wind_forcing_mode = ScenarioIO._choose_wind_mode(
            wind_series,
            wind_constant,
            wind_mean,
            wind_use_constant,
        )
        light_forcing_mode = ScenarioIO._choose_light_mode(
            light_series,
            light_constant,
            light_mean,
            light_range,
            light_use_constant,
        )
        ph_forcing_mode = ScenarioIO._choose_ph_mode(
            ph_series,
            ph_constant,
            ph_use_constant,
        )
        inorganic_mode, tss_forcing_mode = ScenarioIO._choose_inorganic_solids_mode(
            tss_series,
            tss_constant,
            tss_use_constant,
        )

        if volume is None:
            volume = ScenarioIO._prompt_float("Enter lake volume (m^3): ")
        if area is None:
            area = ScenarioIO._prompt_float("Enter surface area (m^2): ")
        if depth_mean is None:
            depth_mean = ScenarioIO._prompt_float("Enter mean depth (m): ")
        if depth_max is None:
            depth_max = ScenarioIO._prompt_float("Enter max depth (m): ")
        if not inflow_series:
            inflow_series = ScenarioIO._prompt_series("inflow")
        if inflow_series and not outflow_series:
            outflow_series = dict(inflow_series)
        if not outflow_series:
            outflow_series = ScenarioIO._prompt_series("outflow")
        if temp_forcing_mode == "mean_range":
            if temp_epi_mean is None:
                temp_epi_mean = ScenarioIO._prompt_float("Enter epilimnion temp mean (deg C): ")
            if temp_epi_range is None:
                temp_epi_range = ScenarioIO._prompt_float("Enter epilimnion temp range (deg C): ")
            if temp_hypo_mean is None:
                temp_hypo_mean = ScenarioIO._prompt_float("Enter hypolimnion temp mean (deg C): ")
            if temp_hypo_range is None:
                temp_hypo_range = ScenarioIO._prompt_float("Enter hypolimnion temp range (deg C): ")
        if wind_forcing_mode == "constant" and wind_constant is None:
            wind_constant = ScenarioIO._prompt_float("Enter constant wind loading (m/s): ")
        if wind_forcing_mode == "default_series":
            if wind_mean is None:
                wind_mean = ScenarioIO._prompt_float(
                    "Enter mean wind value (m/s) for default time series: "
                )
            else:
                prompt = f"Use mean wind value from file ({wind_mean} m/s)? [Y/n]: "
                while True:
                    raw = input(prompt).strip().lower()
                    if raw in ("", "y", "yes"):
                        break
                    if raw in ("n", "no"):
                        wind_mean = ScenarioIO._prompt_float(
                            "Enter mean wind value (m/s) for default time series: "
                        )
                        break
                    print("Enter y or n.")
        if wind_forcing_mode == "time_varying" and not wind_series:
            wind_series = ScenarioIO._prompt_time_series(
                "wind",
                "Wind value per day (m/s): ",
            )
        if light_forcing_mode == "constant" and light_constant is None:
            light_constant = ScenarioIO._prompt_float("Enter constant light loading (Ly/d): ")
        if light_forcing_mode == "mean_range":
            if light_mean is None:
                light_mean = ScenarioIO._prompt_float("Enter mean light value (Ly/d): ")
            if light_range is None:
                light_range = ScenarioIO._prompt_float("Enter light range (Ly/d): ")
        if light_forcing_mode == "time_varying" and not light_series:
            light_series = ScenarioIO._prompt_time_series(
                "light",
                "Light value per day (Ly/d): ",
            )
        if ph_forcing_mode == "constant" and ph_constant is None:
            ph_constant = ScenarioIO._prompt_float("Enter constant pH: ")
        if ph_forcing_mode == "time_varying" and not ph_series:
            ph_series = ScenarioIO._prompt_time_series(
                "pH",
                "pH value per day: ",
            )
        if inorganic_mode == "tss":
            if tss_forcing_mode == "constant" and tss_constant is None:
                tss_constant = ScenarioIO._prompt_float("Enter constant TSS (mg/L): ")
                if tss_initial is None:
                    tss_initial = tss_constant
            if tss_forcing_mode == "time_varying":
                if tss_initial is None:
                    tss_initial = ScenarioIO._prompt_float("Enter initial TSS (mg/L): ")
                if not tss_series:
                    tss_series = ScenarioIO._prompt_time_series(
                        "TSS",
                        "TSS value per day (mg/L): ",
                    )

        return Environment(
            volume=volume,
            area=area,
            depth_mean=depth_mean,
            depth_max=depth_max,
            inflow_series=inflow_series,
            outflow_series=outflow_series,
            temp_epi_series=temp_epi_series,
            temp_hypo_series=temp_hypo_series,
            temp_epi_constant=temp_epi_const,
            temp_hypo_constant=temp_hypo_const,
            temp_epi_mean=temp_epi_mean,
            temp_epi_range=temp_epi_range,
            temp_hypo_mean=temp_hypo_mean,
            temp_hypo_range=temp_hypo_range,
            temp_forcing_mode=temp_forcing_mode,
            wind_series=wind_series,
            wind_constant=wind_constant,
            wind_mean=wind_mean,
            wind_forcing_mode=wind_forcing_mode,
            light_series=light_series,
            light_constant=light_constant,
            light_mean=light_mean,
            light_range=light_range,
            light_forcing_mode=light_forcing_mode,
            ph_series=ph_series,
            ph_constant=ph_constant,
            ph_forcing_mode=ph_forcing_mode,
            tss_series=tss_series,
            tss_constant=tss_constant,
            tss_initial=tss_initial,
            tss_forcing_mode=tss_forcing_mode,
            inorganic_solids_mode=inorganic_mode,
        )

    @staticmethod
    def _parse_inflow_series(text: str) -> Dict[datetime, float]:
        inflow_series, _ = ScenarioIO._parse_water_volume_series(text)
        return inflow_series

    @staticmethod
    def _parse_outflow_series(text: str) -> Dict[datetime, float]:
        _, outflow_series = ScenarioIO._parse_water_volume_series(text)
        return outflow_series

    @staticmethod
    def _parse_temperature_series(text: str) -> tuple[Dict[datetime, float], Dict[datetime, float]]:
        epi_series: Dict[datetime, float] = {}
        hypo_series: Dict[datetime, float] = {}

        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Temperature":
                epi_series = ScenarioIO._parse_time_series_from_block(block)
                break

        hypo_block = ScenarioIO._extract_named_block(text, "HypoTempLoads LoadingsRecord")
        if hypo_block:
            hypo_series = ScenarioIO._parse_time_series_from_block(hypo_block)

        return epi_series, hypo_series

    @staticmethod
    def _parse_temperature_constants(text: str) -> tuple[float | None, float | None]:
        epi_const = None
        hypo_const = ScenarioIO._find_float(text, r'"HypoTempIC":\s*([-\d.E+]+)')
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Temperature":
                epi_const = ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')
                break
        return epi_const, hypo_const

    @staticmethod
    def _parse_temperature_mean_range(
        text: str,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        epi_mean = ScenarioIO._find_float(text, r'"TempMean\[epilimnion\]":\s*([-\d.E+]+)')
        epi_range = ScenarioIO._find_float(text, r'"TempRange\[epilimnion\]":\s*([-\d.E+]+)')
        hypo_mean = ScenarioIO._find_float(text, r'"TempMean\[Hypolimnion\]":\s*([-\d.E+]+)')
        hypo_range = ScenarioIO._find_float(text, r'"TempRange\[Hypolimnion\]":\s*([-\d.E+]+)')
        return epi_mean, epi_range, hypo_mean, hypo_range

    @staticmethod
    def _parse_wind_series(text: str) -> Dict[datetime, float]:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Wind Loading":
                return ScenarioIO._parse_time_series_from_block(block)
        return {}

    @staticmethod
    def _parse_wind_constant(text: str) -> float | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') != "Wind Loading":
                continue
            const_value = ScenarioIO._find_float(block, r'"ConstLoad":\s*([-\d.E+]+)')
            if const_value is not None:
                return const_value
            return ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')
        return None

    @staticmethod
    def _parse_wind_mean(text: str) -> float | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Wind Loading":
                return ScenarioIO._find_float(block, r'"TWindLoading\.MeanValue":\s*([-\d.E+]+)')
        return None

    @staticmethod
    def _parse_wind_use_constant(text: str) -> bool | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Wind Loading":
                raw = ScenarioIO._find_str(block, r'"UseConstant":\s*(TRUE|FALSE)')
                if raw is None:
                    return None
                return raw.upper() == "TRUE"
        return None

    @staticmethod
    def _parse_light_series(text: str) -> Dict[datetime, float]:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Light":
                return ScenarioIO._parse_time_series_from_block(block)
        return {}

    @staticmethod
    def _parse_light_constant(text: str) -> float | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') != "Light":
                continue
            const_value = ScenarioIO._find_float(block, r'"ConstLoad":\s*([-\d.E+]+)')
            if const_value is not None:
                return const_value
            return ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')
        return None

    @staticmethod
    def _parse_light_mean_range(text: str) -> tuple[float | None, float | None]:
        light_mean = ScenarioIO._find_float(text, r'"LightMean":\s*([-\d.E+]+)')
        light_range = ScenarioIO._find_float(text, r'"LightRange":\s*([-\d.E+]+)')
        return light_mean, light_range

    @staticmethod
    def _parse_light_use_constant(text: str) -> bool | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "Light":
                raw = ScenarioIO._find_str(block, r'"UseConstant":\s*(TRUE|FALSE)')
                if raw is None:
                    return None
                return raw.upper() == "TRUE"
        return None

    @staticmethod
    def _parse_ph_series(text: str) -> Dict[datetime, float]:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "pH":
                return ScenarioIO._parse_time_series_from_block(block)
        return {}

    @staticmethod
    def _parse_ph_constant(text: str) -> float | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') != "pH":
                continue
            const_value = ScenarioIO._find_float(block, r'"ConstLoad":\s*([-\d.E+]+)')
            if const_value is not None:
                return const_value
            return ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')
        return None

    @staticmethod
    def _parse_ph_use_constant(text: str) -> bool | None:
        for block in ScenarioIO._extract_state_blocks(text):
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') == "pH":
                raw = ScenarioIO._find_str(block, r'"UseConstant":\s*(TRUE|FALSE)')
                if raw is None:
                    return None
                return raw.upper() == "TRUE"
        return None

    @staticmethod
    def _parse_tss_series(text: str) -> Dict[datetime, float]:
        block = ScenarioIO._find_tss_block(text)
        if not block:
            return {}
        return ScenarioIO._parse_time_series_from_block(block)

    @staticmethod
    def _parse_tss_constant(text: str) -> float | None:
        block = ScenarioIO._find_tss_block(text)
        if not block:
            return None
        const_value = ScenarioIO._find_float(block, r'"ConstLoad":\s*([-\d.E+]+)')
        if const_value is not None:
            return const_value
        return ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')

    @staticmethod
    def _parse_tss_initial(text: str) -> float | None:
        block = ScenarioIO._find_tss_block(text)
        if not block:
            return None
        return ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')

    @staticmethod
    def _parse_tss_use_constant(text: str) -> bool | None:
        block = ScenarioIO._find_tss_block(text)
        if not block:
            return None
        raw = ScenarioIO._find_str(block, r'"UseConstant":\s*(TRUE|FALSE)')
        if raw is None:
            return None
        return raw.upper() == "TRUE"

    @staticmethod
    def _find_tss_block(text: str) -> str | None:
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            lower = name.lower()
            if lower == "tss":
                return block
            if "susp" in lower and "solid" in lower:
                return block
            if "total suspended" in lower:
                return block
        return None

    @staticmethod
    def _choose_temperature_mode(
        epi_series: Dict[datetime, float],
        hypo_series: Dict[datetime, float],
        epi_mean: float | None,
        epi_range: float | None,
        hypo_mean: float | None,
        hypo_range: float | None,
    ) -> str:
        has_series = bool(epi_series) or bool(hypo_series)
        has_mean_range = (
            epi_mean is not None
            and epi_range is not None
            and hypo_mean is not None
            and hypo_range is not None
        )
        if not has_series and not has_mean_range:
            return "constant"
        if has_series:
            prompt = "Use time-series forcing for temperature? [Y/n]: "
            while True:
                raw = input(prompt).strip().lower()
                if raw in ("", "y", "yes"):
                    interp_prompt = "Allow interpolation for missing dates? [Y/n]: "
                    while True:
                        interp_raw = input(interp_prompt).strip().lower()
                        if interp_raw in ("", "y", "yes"):
                            return "series_interpolate"
                        if interp_raw in ("n", "no"):
                            return "series"
                        print("Enter y or n.")
                if raw in ("n", "no"):
                    break
                print("Enter y or n.")
        if has_mean_range:
            prompt = "Use annual mean/range for temperature? [Y/n]: "
            while True:
                raw = input(prompt).strip().lower()
                if raw in ("", "y", "yes"):
                    return "mean_range"
                if raw in ("n", "no"):
                    break
                print("Enter y or n.")
        return "constant"

    @staticmethod
    def _choose_wind_mode(
        wind_series: Dict[datetime, float],
        wind_constant: float | None,
        wind_mean: float | None,
        wind_use_constant: bool | None,
    ) -> str:
        has_series = bool(wind_series)
        has_constant = wind_constant is not None
        has_mean = wind_mean is not None

        if wind_use_constant is True and has_constant:
            return "constant"
        if wind_use_constant is False and (has_series or has_mean):
            default_mode = "time_varying"
        elif has_mean:
            default_mode = "default_series"
        elif has_constant:
            default_mode = "constant"
        else:
            default_mode = "time_varying"

        print("Wind loading options:")
        print("  1) Enter constant wind")
        print("  2) Use default time series (365-day Fourier)")
        print("  3) Use time-varying wind (annual wrap of series)")
        default_label = {
            "constant": "1",
            "default_series": "2",
            "time_varying": "3",
        }[default_mode]
        while True:
            raw = input(f"Select wind loading mode [default {default_label}]: ").strip().lower()
            if raw == "":
                return default_mode
            if raw in ("1", "constant", "const"):
                return "constant"
            if raw in ("2", "default", "default_series", "default time series"):
                return "default_series"
            if raw in ("3", "time", "time-varying", "timevarying"):
                return "time_varying"
            print("Enter 1, 2, or 3.")

    @staticmethod
    def _choose_light_mode(
        light_series: Dict[datetime, float],
        light_constant: float | None,
        light_mean: float | None,
        light_range: float | None,
        light_use_constant: bool | None,
    ) -> str:
        has_series = bool(light_series)
        has_constant = light_constant is not None
        has_mean_range = light_mean is not None and light_range is not None

        if light_use_constant is True and has_constant:
            return "constant"
        if light_use_constant is False and has_series:
            default_mode = "time_varying"
        elif has_mean_range:
            default_mode = "mean_range"
        elif has_series:
            default_mode = "time_varying"
        elif has_constant:
            default_mode = "constant"
        else:
            default_mode = "constant"

        print("Light loading options:")
        print("  1) Enter constant light")
        print("  2) Use annual mean and range")
        print("  3) Use time-varying light")
        default_label = {
            "constant": "1",
            "mean_range": "2",
            "time_varying": "3",
        }[default_mode]
        while True:
            raw = input(f"Select light loading mode [default {default_label}]: ").strip().lower()
            if raw == "":
                return default_mode
            if raw in ("1", "constant", "const"):
                return "constant"
            if raw in ("2", "mean", "mean_range", "annual", "range"):
                return "mean_range"
            if raw in ("3", "time", "time-varying", "timevarying"):
                return "time_varying"
            print("Enter 1, 2, or 3.")

    @staticmethod
    def _choose_ph_mode(
        ph_series: Dict[datetime, float],
        ph_constant: float | None,
        ph_use_constant: bool | None,
    ) -> str:
        has_series = bool(ph_series)
        has_constant = ph_constant is not None

        if ph_use_constant is True and has_constant:
            return "constant"
        if ph_use_constant is False and has_series:
            default_mode = "time_varying"
        elif has_series:
            default_mode = "time_varying"
        elif has_constant:
            default_mode = "constant"
        else:
            default_mode = "constant"

        print("pH loading options:")
        print("  1) Enter constant pH")
        print("  2) Use time-varying pH")
        default_label = {
            "constant": "1",
            "time_varying": "2",
        }[default_mode]
        while True:
            raw = input(f"Select pH loading mode [default {default_label}]: ").strip().lower()
            if raw == "":
                return default_mode
            if raw in ("1", "constant", "const"):
                return "constant"
            if raw in ("2", "time", "time-varying", "timevarying"):
                return "time_varying"
            print("Enter 1 or 2.")

    @staticmethod
    def _choose_inorganic_solids_mode(
        tss_series: Dict[datetime, float],
        tss_constant: float | None,
        tss_use_constant: bool | None,
    ) -> tuple[str, str]:
        has_series = bool(tss_series)
        has_constant = tss_constant is not None

        if tss_use_constant is True and has_constant:
            default_tss_mode = "constant"
        elif tss_use_constant is False and has_series:
            default_tss_mode = "time_varying"
        elif has_series:
            default_tss_mode = "time_varying"
        elif has_constant:
            default_tss_mode = "constant"
        else:
            default_tss_mode = "constant"

        print("Do you wish to simulate Inorganic Solids within the system?")
        print("  1) No, don't simulate inorganics")
        print("  2) Yes, simulate TSS")
        print("  3) Yes, use Sand-Silt-Clay Model")
        while True:
            raw = input("Select inorganic solids mode [default 1]: ").strip().lower()
            if raw == "" or raw in ("1", "no", "none"):
                return "none", "none"
            if raw in ("2", "tss", "yes"):
                break
            if raw in ("3", "sand", "sand-silt-clay", "sand silt clay"):
                return "sand_silt_clay", "none"
            print("Enter 1, 2, or 3.")

        print("TSS options:")
        print("  1) Enter constant TSS")
        print("  2) Use time-varying TSS (annual wrap of series)")
        default_label = "1" if default_tss_mode == "constant" else "2"
        while True:
            raw = input(f"Select TSS mode [default {default_label}]: ").strip().lower()
            if raw == "":
                return "tss", default_tss_mode
            if raw in ("1", "constant", "const"):
                return "tss", "constant"
            if raw in ("2", "time", "time-varying", "timevarying"):
                return "tss", "time_varying"
            print("Enter 1 or 2.")

    @staticmethod
    def _parse_water_volume_series(text: str) -> tuple[Dict[datetime, float], Dict[datetime, float]]:
        blocks = ScenarioIO._extract_state_blocks(text)
        for block in blocks:
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') != "Water Volume":
                continue
            series_by_section = ScenarioIO._collect_alt_series(block)
            inflow_series = ScenarioIO._pick_series(
                series_by_section,
                [
                    "LoadingsRecord",
                    "Point Source Loadings",
                    "NonPoint Source Loadings",
                    "Direct Precip Loadings",
                ],
            )
            outflow_series = ScenarioIO._pick_series(
                series_by_section,
                ["Direct Precip Loadings"],
            )
            return inflow_series, outflow_series
        return {}, {}

    @staticmethod
    def _collect_alt_series(block: str) -> Dict[str, list[Dict[datetime, float]]]:
        headers: list[tuple[int, str]] = []
        for label in (
            "Direct Precip Loadings",
            "NonPoint Source Loadings",
            "Point Source Loadings",
            "LoadingsRecord",
        ):
            if label == "LoadingsRecord":
                pattern = r'" LoadingsRecord":\s*{'
            else:
                pattern = re.escape(label + ":")
            for match in re.finditer(pattern, block):
                headers.append((match.start(), label))
        headers.sort(key=lambda item: item[0])

        series_by_section: Dict[str, list[Dict[datetime, float]]] = {}
        for match in re.finditer(
            r"Alt\. Time Series Loadings:\s*n=\d+;(.+?)(?=\n\s*\"Alt_MultLdg\"|\n\s*Direct Precip Loadings:|\n\s*NonPoint Source Loadings:|\n\s*Point Source Loadings:|$)",
            block,
            re.DOTALL,
        ):
            section = "LoadingsRecord"
            for pos, label in headers:
                if pos <= match.start():
                    section = label
                else:
                    break
            parsed = ScenarioIO._parse_time_series(match.group(1).strip())
            if parsed:
                series_by_section.setdefault(section, []).append(parsed)
        return series_by_section

    @staticmethod
    def _pick_series(
        series_by_section: Dict[str, list[Dict[datetime, float]]],
        priority: list[str],
    ) -> Dict[datetime, float]:
        for section in priority:
            series_list = series_by_section.get(section, [])
            if series_list:
                series_list.sort(key=len, reverse=True)
                return series_list[0]
        return {}

    @staticmethod
    def _parse_time_series_from_block(block: str) -> Dict[datetime, float]:
        match = re.search(
            r"Time Series Loadings:\s*n=\d+;(.+?)(?=\n\s*\"MultLdg\"|\n\s*\"LoadsRec\.MultLdg\"|\n\s*\"PRequiresData\^\"|$)",
            block,
            re.DOTALL,
        )
        if not match:
            return {}
        return ScenarioIO._parse_time_series(match.group(1).strip())

    @staticmethod
    def _parse_state_variables(text: str) -> list[StateVariable]:
        state_vars: list[StateVariable] = []
        for record in ScenarioIO._parse_state_records(text):
            state_vars.append(ScenarioIO._make_state_var(record))
        return state_vars

    @staticmethod
    def _prompt_state_variables() -> list[StateVariable]:
        count = ScenarioIO._prompt_int("How many state variables to initialize? ")
        records: list[dict] = []
        for idx in range(1, count + 1):
            name = ScenarioIO._prompt_text(f"{idx}. name: ")
            value = ScenarioIO._prompt_float(f"{idx}. initial value: ")
            units = ScenarioIO._prompt_text(f"{idx}. units: ")
            records.append({"name": name, "initial": value, "units": units})
        return [ScenarioIO._make_state_var(record) for record in records]

    @staticmethod
    def _make_state_var(record: dict) -> StateVariable:
        name = record["name"]
        value = record["initial"]
        units = record.get("units") or "arb"
        lower = name.lower()
        if "nitrate" in lower or "no3" in lower:
            return Nutrient(name=name, value=value, units=units, form="NO3")
        if "ammonia" in lower or "nh4" in lower:
            return Nutrient(name=name, value=value, units=units, form="NH4")
        if "phosphate" in lower or "po4" in lower:
            return Nutrient(name=name, value=value, units=units, form="PO4")
        if "oxygen" in lower or "o2" in lower:
            return Nutrient(name=name, value=value, units=units, form="O2")
        if "co2" in lower:
            return Nutrient(name=name, value=value, units=units, form="CO2")
        if "detritus" in lower:
            detritus_type = "refractory" if "refrac" in lower else "labile"
            layer = "sediment" if "sed" in lower else "water"
            return Detritus(name=name, value=value, units=units, type=detritus_type, layer=layer)
        if ScenarioIO._looks_like_plant(lower):
            return Plant(
                name=name,
                value=value,
                units=units,
                biomass=value,
                max_growth=0.0,
                mortality_rate=0.0,
                nutrient_uptake_rate=0.0,
            )
        if ScenarioIO._looks_like_animal(lower):
            return Animal(
                name=name,
                value=value,
                units=units,
                biomass=value,
                max_growth=0.0,
                mortality_rate=0.0,
                feeding_prefs={},
                consumption_rate=0.0,
            )
        return StateVariable(name=name, value=value, units=units)

    @staticmethod
    def _looks_like_plant(name: str) -> bool:
        return any(token in name for token in ("diatoms", "greens", "cyanobacteria", "otheralg"))

    @staticmethod
    def _looks_like_animal(name: str) -> bool:
        return any(token in name for token in ("feeder", "fish", "zooplank", "chironomid", "oligochaete"))

    @staticmethod
    def _parse_state_records(text: str) -> list[dict]:
        records: list[dict] = []
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            value = ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')
            if value is None:
                continue
            units = ScenarioIO._find_str(block, r'"StateUnit":\s*"([^"]+)"') or "arb"
            records.append({"name": name, "initial": value, "units": units})
        return records

    @staticmethod
    def _parse_foodweb_from_scenario(text: str):
        state_index: Dict[int, str] = {}
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            idx = ScenarioIO._find_int(block, r'"nState":\s*(\d+)')
            if name and idx is not None:
                state_index[idx] = name

        interactions = []
        for animal_block in ScenarioIO._extract_blocks(text, "TAnimal"):
            predator_name = ScenarioIO._find_str(animal_block, r'"PName\^":\s*"([^"]+)"')
            if not predator_name:
                continue
            troph_block = ScenarioIO._extract_named_block(animal_block, "TrophInt")
            if troph_block is None:
                continue
            pref_map, ecoeff_map = ScenarioIO._parse_trophint_block(troph_block)
            for idx, pref in pref_map.items():
                ecoeff = ecoeff_map.get(idx)
                if (pref is None or pref <= 0.0) and (ecoeff is None or ecoeff <= 0.0):
                    continue
                prey_name = state_index.get(idx)
                if not prey_name:
                    continue
                interactions.append(
                    {
                        "predator": predator_name,
                        "prey": prey_name,
                        "pref": pref,
                        "egestion": ecoeff,
                    }
                )

        if not interactions:
            return None

        from .foodweb import FoodWeb, FoodWebInteraction

        return FoodWeb(
            interactions=[
                FoodWebInteraction(
                    predator=item["predator"],
                    prey=item["prey"],
                    observations=0,
                    params=[],
                    diet_percent=item["pref"],
                    habitat_code=None,
                    egestion_coeff=item["egestion"],
                )
                for item in interactions
            ],
            preference_source="diet_percent",
        )

    @staticmethod
    def _extract_blocks(text: str, marker: str) -> list[str]:
        blocks: list[str] = []
        lines = text.splitlines()
        in_block = False
        depth = 0
        buffer: list[str] = []
        tag = f'"{marker}": {{'
        for line in lines:
            if not in_block and tag in line:
                in_block = True
                depth = 0
                buffer = [line]
                depth += line.count("{") - line.count("}")
                continue
            if in_block:
                buffer.append(line)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    blocks.append("\n".join(buffer))
                    in_block = False
        return blocks

    @staticmethod
    def _extract_named_block(text: str, marker: str) -> str | None:
        lines = text.splitlines()
        in_block = False
        depth = 0
        buffer: list[str] = []
        tag = f'"{marker}": {{'
        for line in lines:
            if not in_block and tag in line:
                in_block = True
                depth = 0
                buffer = [line]
                depth += line.count("{") - line.count("}")
                continue
            if in_block:
                buffer.append(line)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    return "\n".join(buffer)
        return None

    @staticmethod
    def _parse_trophint_block(block: str) -> tuple[Dict[int, float], Dict[int, float]]:
        pref_map: Dict[int, float] = {}
        ecoeff_map: Dict[int, float] = {}
        for match in re.finditer(r'"Pref(\d+)":\s*([-\d.E+]+)', block):
            idx = int(match.group(1))
            pref_map[idx] = ScenarioIO._safe_float(match.group(2))
        for match in re.finditer(r'"ECoeff(\d+)":\s*([-\d.E+]+)', block):
            idx = int(match.group(1))
            ecoeff_map[idx] = ScenarioIO._safe_float(match.group(2))
        return pref_map, ecoeff_map

    @staticmethod
    def _extract_state_blocks(text: str) -> list[str]:
        blocks: list[str] = []
        lines = text.splitlines()
        in_block = False
        depth = 0
        buffer: list[str] = []
        for line in lines:
            if not in_block and '"TStateVariable": {' in line:
                in_block = True
                depth = 0
                buffer = [line]
                depth += line.count("{") - line.count("}")
                continue
            if in_block:
                buffer.append(line)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    blocks.append("\n".join(buffer))
                    in_block = False
        return blocks

    @staticmethod
    def _apply_tss_initial(state_vars: list[StateVariable], tss_initial: float) -> None:
        for sv in state_vars:
            name = sv.name.lower()
            if name == "tss" or ("susp" in name and "solid" in name) or "total suspended" in name:
                sv.value = tss_initial
                break

    @staticmethod
    def _parse_inflow_loadings(text: str) -> list[dict]:
        loadings: list[dict] = []
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            no_user_load_raw = ScenarioIO._find_str(block, r'"NoUserLoad":\s*(TRUE|FALSE)')
            use_constant_raw = ScenarioIO._find_str(block, r'"UseConstant":\s*(TRUE|FALSE)')
            const_load = ScenarioIO._find_float(block, r'"ConstLoad":\s*([-\d.E+]+)')
            mult_ldg = ScenarioIO._find_float(block, r'"MultLdg":\s*([-\d.E+]+)')
            units = ScenarioIO._find_str(block, r'"LoadingUnit":\s*"([^"]+)"')
            if units is None:
                units = ScenarioIO._find_str(block, r'"StateUnit":\s*"([^"]+)"') or "arb"
            series = ScenarioIO._parse_time_series_from_block(block)

            loadings.append(
                {
                    "name": name,
                    "units": units,
                    "no_user_load": True if no_user_load_raw == "TRUE" else False,
                    "use_constant": True if use_constant_raw == "TRUE" else False,
                    "const_load": const_load,
                    "mult_ldg": mult_ldg,
                    "series": series,
                }
            )
        return loadings

    @staticmethod
    def _extract_loadings_section(block: str, label: str) -> str | None:
        pattern = (
            rf"{re.escape(label)}\s*(.+?)(?=\n\s*Point Source Loadings:|\n\s*Direct Precip Loadings:|"
            r"\n\s*NonPoint Source Loadings:|\n\s*\"PRequiresData\^\"|\n\s*\"StateUnit\"|$)"
        )
        match = re.search(pattern, block, re.DOTALL)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def _parse_alt_loadings_section(section: str) -> dict:
        use_constant_raw = ScenarioIO._find_str(section, r'"Alt_UseConstant":\s*(TRUE|FALSE)')
        const_load = ScenarioIO._find_float(section, r'"Alt_ConstLoad":\s*([-\d.E+]+)')
        mult_ldg = ScenarioIO._find_float(section, r'"Alt_MultLdg":\s*([-\d.E+]+)')
        series = {}
        match = re.search(
            r"Alt\.\s*Time Series Loadings:\s*n=\d+;(.+?)(?=\n\s*\"Alt_MultLdg\"|$)",
            section,
            re.DOTALL,
        )
        if match:
            series = ScenarioIO._parse_time_series(match.group(1).strip())
        return {
            "use_constant": True if use_constant_raw == "TRUE" else False,
            "const_load": const_load,
            "mult_ldg": mult_ldg,
            "series": series,
        }

    @staticmethod
    def _parse_direct_precip_loadings(text: str) -> list[dict]:
        loadings: list[dict] = []
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            no_user_load_raw = ScenarioIO._find_str(block, r'"NoUserLoad":\s*(TRUE|FALSE)')
            units = ScenarioIO._find_str(block, r'"LoadingUnit":\s*"([^"]+)"')
            if units is None:
                units = ScenarioIO._find_str(block, r'"StateUnit":\s*"([^"]+)"') or "arb"

            section = ScenarioIO._extract_loadings_section(block, "Direct Precip Loadings:")
            if section is None:
                continue
            parsed = ScenarioIO._parse_alt_loadings_section(section)

            loadings.append(
                {
                    "name": name,
                    "units": units,
                    "no_user_load": True if no_user_load_raw == "TRUE" else False,
                    "use_constant": parsed["use_constant"],
                    "const_load": parsed["const_load"],
                    "mult_ldg": parsed["mult_ldg"],
                    "series": parsed["series"],
                }
            )
        return loadings

    @staticmethod
    def _parse_point_source_loadings(text: str) -> list[dict]:
        loadings: list[dict] = []
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            no_user_load_raw = ScenarioIO._find_str(block, r'"NoUserLoad":\s*(TRUE|FALSE)')
            units = ScenarioIO._find_str(block, r'"LoadingUnit":\s*"([^"]+)"')
            if units is None:
                units = ScenarioIO._find_str(block, r'"StateUnit":\s*"([^"]+)"') or "arb"

            section = ScenarioIO._extract_loadings_section(block, "Point Source Loadings:")
            if section is None:
                continue
            parsed = ScenarioIO._parse_alt_loadings_section(section)

            loadings.append(
                {
                    "name": name,
                    "units": units,
                    "no_user_load": True if no_user_load_raw == "TRUE" else False,
                    "use_constant": parsed["use_constant"],
                    "const_load": parsed["const_load"],
                    "mult_ldg": parsed["mult_ldg"],
                    "series": parsed["series"],
                }
            )
        return loadings

    @staticmethod
    def _parse_nonpoint_source_loadings(text: str) -> list[dict]:
        loadings: list[dict] = []
        for block in ScenarioIO._extract_state_blocks(text):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            no_user_load_raw = ScenarioIO._find_str(block, r'"NoUserLoad":\s*(TRUE|FALSE)')
            units = ScenarioIO._find_str(block, r'"LoadingUnit":\s*"([^"]+)"')
            if units is None:
                units = ScenarioIO._find_str(block, r'"StateUnit":\s*"([^"]+)"') or "arb"

            section = ScenarioIO._extract_loadings_section(block, "NonPoint Source Loadings:")
            if section is None:
                continue
            parsed = ScenarioIO._parse_alt_loadings_section(section)

            loadings.append(
                {
                    "name": name,
                    "units": units,
                    "no_user_load": True if no_user_load_raw == "TRUE" else False,
                    "use_constant": parsed["use_constant"],
                    "const_load": parsed["const_load"],
                    "mult_ldg": parsed["mult_ldg"],
                    "series": parsed["series"],
                }
            )
        return loadings

    @staticmethod
    def _parse_chemicals(text: str) -> list[dict]:
        loadchem_map: Dict[int, bool] = {}
        for match in re.finditer(r'"LoadChem(\d+)":\s*(TRUE|FALSE)', text):
            idx = int(match.group(1))
            loadchem_map[idx] = match.group(2).upper() == "TRUE"

        chemicals: list[dict] = []
        for idx, block in enumerate(ScenarioIO._extract_blocks(text, "ChemicalRecord"), start=1):
            name = ScenarioIO._find_str(block, r'"ChemName":\s*"([^"]+)"')
            if not name:
                continue
            active = loadchem_map.get(idx, True if not loadchem_map else False)
            chemicals.append({"index": idx, "name": name, "active": active})

        if chemicals:
            return chemicals

        for block in ScenarioIO._extract_blocks(text, "TToxics"):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            match = re.search(r"tox\s*(\d+)\s*:\s*\[([^\]]+)\]", name, re.IGNORECASE)
            if not match:
                continue
            idx = int(match.group(1))
            chem_name = match.group(2).strip()
            chemicals.append({"index": idx, "name": chem_name, "active": True})

        chemicals.sort(key=lambda item: item["index"])
        return chemicals

    @staticmethod
    def _parse_chemical_states(text: str, chemicals: list[dict]) -> list[dict]:
        chem_name_by_index = {item["index"]: item["name"] for item in chemicals}
        states: list[dict] = []
        for block in ScenarioIO._extract_blocks(text, "TToxics"):
            name = ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"')
            if not name:
                continue
            initial = ScenarioIO._find_float(block, r'"InitialCond":\s*([-\d.E+]+)')
            if initial is None:
                continue
            units = ScenarioIO._find_str(block, r'"StateUnit":\s*"([^"]+)"') or "arb"
            carrier = ScenarioIO._find_int(block, r'"Carrier":\s*(\d+)')
            ppb = ScenarioIO._find_float(block, r'"ppb":\s*([-\d.E+]+)')
            chem_index = None
            chem_name = None
            match = re.search(r"tox\s*(\d+)\s*:\s*\[([^\]]+)\]", name, re.IGNORECASE)
            if match:
                chem_index = int(match.group(1))
                chem_name = match.group(2).strip()
            if chem_index is not None and chem_name is None:
                chem_name = chem_name_by_index.get(chem_index)
            states.append(
                {
                    "name": name,
                    "initial": initial,
                    "units": units,
                    "carrier": carrier,
                    "ppb": ppb,
                    "chem_index": chem_index,
                    "chem_name": chem_name,
                }
            )
        return states

    @staticmethod
    def _parse_time_series(series_blob: str) -> Dict[datetime, float]:
        entries = [seg.strip() for seg in series_blob.split(";") if seg.strip()]
        series: Dict[datetime, float] = {}
        for entry in entries:
            if "," not in entry:
                continue
            date_text, value_text = entry.split(",", 1)
            date_text = date_text.strip()
            value_text = value_text.strip()
            timestamp = ScenarioIO._parse_date(date_text)
            if timestamp is None:
                continue
            try:
                value = float(value_text)
            except ValueError:
                continue
            series[timestamp] = value
        return series

    @staticmethod
    def _parse_date(raw: str) -> datetime | None:
        for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _prompt_series(label: str) -> Dict[datetime, float]:
        print(f"Series not found in file ({label}); enter values via CLI.")
        start = ScenarioIO._prompt_date(f"{label} start date (dd/mm/yyyy): ")
        days = ScenarioIO._prompt_int(f"{label} number of days: ")
        value = ScenarioIO._prompt_float(f"{label} value per day (m^3/day): ")
        return {start + timedelta(days=i): value for i in range(days)}

    @staticmethod
    def _prompt_time_series(label: str, value_prompt: str) -> Dict[datetime, float]:
        print(f"Series not found in file ({label}); enter values via CLI.")
        start = ScenarioIO._prompt_date(f"{label} start date (dd/mm/yyyy): ")
        days = ScenarioIO._prompt_int(f"{label} number of days: ")
        series: Dict[datetime, float] = {}
        for offset in range(days):
            value = ScenarioIO._prompt_float(value_prompt)
            series[start + timedelta(days=offset)] = value
        return series

    @staticmethod
    def _prompt_text(prompt: str) -> str:
        while True:
            value = input(prompt).strip()
            if value:
                return value
            print("Input cannot be empty.")

    @staticmethod
    def _prompt_float(prompt: str) -> float:
        while True:
            raw = input(prompt).strip()
            try:
                return float(raw)
            except ValueError:
                print("Enter a valid number.")

    @staticmethod
    def _prompt_int(prompt: str) -> int:
        while True:
            raw = input(prompt).strip()
            try:
                value = int(raw)
            except ValueError:
                print("Enter an integer.")
                continue
            if value > 0:
                return value
            print("Enter a positive integer.")

    @staticmethod
    def _prompt_date(prompt: str) -> datetime:
        while True:
            raw = input(prompt).strip()
            try:
                return datetime.strptime(raw, "%d/%m/%Y")
            except ValueError:
                print("Enter a date in dd/mm/yyyy format.")

    @staticmethod
    def _find_float(text: str, pattern: str) -> float | None:
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _find_str(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def _find_int(text: str, pattern: str) -> int | None:
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _safe_float(raw: str) -> float:
        try:
            return float(raw)
        except ValueError:
            return 0.0

    @staticmethod
    def export_state_variables(file: str, json_path: str, csv_path: str) -> list[dict]:
        path = Path(file)
        text = path.read_text(encoding="utf-8", errors="ignore")
        records = ScenarioIO._parse_state_records(text)
        mapping = []
        for record in records:
            obj = ScenarioIO._make_state_var(record)
            mapping.append(
                {
                    "name": record["name"],
                    "initial": record["initial"],
                    "units": record.get("units"),
                    "mapped_class": obj.__class__.__name__,
                }
            )
        json_out = Path(json_path)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        csv_out = Path(csv_path)
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        with csv_out.open("w", encoding="utf-8", newline="") as handle:
            import csv

            writer = csv.DictWriter(handle, fieldnames=["name", "initial", "units", "mapped_class"])
            writer.writeheader()
            writer.writerows(mapping)
        return mapping

    @staticmethod
    def load_forcing(file: str) -> dict:
        # Placeholder for later: inflow/load time series, meteorology, etc.
        return {}

    @staticmethod
    def save_output(results, file: str) -> None:
        # Minimal CSV-like writer
        if not results:
            return
        import csv
        times, first = results[0]
        names = sorted(first.keys())
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time"] + names)
            for t, snapshot in results:
                w.writerow(
                    [t.isoformat()]
                    + [ScenarioIO._format_excel_cell(snapshot.get(n, "")) for n in names]
                )

    @staticmethod
    def save_waterflow_output(results, file: str) -> None:
        if not results:
            return
        import csv

        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "volume_m3", "inflow_m3_per_day", "outflow_m3_per_day"])
            for t, snapshot in results:
                w.writerow(
                    [
                        t.isoformat(),
                        ScenarioIO._format_excel_cell(snapshot.get("volume_m3", "")),
                        ScenarioIO._format_excel_cell(snapshot.get("inflow_m3_per_day", "")),
                        ScenarioIO._format_excel_cell(snapshot.get("outflow_m3_per_day", "")),
                    ]
                )

    @staticmethod
    def save_inflow_outflow_series(
        inflow_series: Dict[datetime, float],
        outflow_series: Dict[datetime, float],
        file: str,
    ) -> None:
        if not inflow_series and not outflow_series:
            return
        import csv

        keys = sorted(set(inflow_series.keys()) | set(outflow_series.keys()))
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "inflow_m3_per_day", "outflow_m3_per_day"])
            for t in keys:
                w.writerow(
                    [
                        t.isoformat(),
                        ScenarioIO._format_excel_cell(inflow_series.get(t, "")),
                        ScenarioIO._format_excel_cell(outflow_series.get(t, "")),
                    ]
                )

    @staticmethod
    def save_temperature_series(
        epi_series: Dict[datetime, float],
        hypo_series: Dict[datetime, float],
        file: str,
    ) -> None:
        if not epi_series and not hypo_series:
            return
        import csv

        keys = sorted(set(epi_series.keys()) | set(hypo_series.keys()))
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "temp_epi_degC", "temp_hypo_degC"])
            for t in keys:
                epi_value = ScenarioIO._format_excel_number(epi_series.get(t))
                hypo_value = ScenarioIO._format_excel_number(hypo_series.get(t))
                w.writerow([t.strftime("%d.%m.%Y"), epi_value, hypo_value])

    @staticmethod
    def save_wind_series(
        wind_series: Dict[datetime, float],
        file: str,
    ) -> None:
        if not wind_series:
            return
        import csv

        keys = sorted(wind_series.keys())
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "wind_m_s"])
            for t in keys:
                wind_value = ScenarioIO._format_excel_number(wind_series.get(t))
                w.writerow([t.strftime("%d.%m.%Y"), wind_value])

    @staticmethod
    def save_light_series(
        light_series: Dict[datetime, float],
        file: str,
    ) -> None:
        if not light_series:
            return
        import csv

        keys = sorted(light_series.keys())
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "light_ly_d"])
            for t in keys:
                light_value = ScenarioIO._format_excel_number(light_series.get(t))
                w.writerow([t.strftime("%d.%m.%Y"), light_value])

    @staticmethod
    def save_ph_series(
        ph_series: Dict[datetime, float],
        file: str,
    ) -> None:
        if not ph_series:
            return
        import csv

        keys = sorted(ph_series.keys())
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "ph"])
            for t in keys:
                ph_value = ScenarioIO._format_excel_number(ph_series.get(t))
                w.writerow([t.strftime("%d.%m.%Y"), ph_value])

    @staticmethod
    def save_tss_series(
        tss_series: Dict[datetime, float],
        file: str,
    ) -> None:
        if not tss_series:
            return
        import csv

        keys = sorted(tss_series.keys())
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["time", "tss_mg_l"])
            for t in keys:
                tss_value = ScenarioIO._format_excel_number(tss_series.get(t))
                w.writerow([t.strftime("%d.%m.%Y"), tss_value])

    @staticmethod
    def save_chemical_states(
        states: list[dict],
        file: str,
    ) -> None:
        if not states:
            return
        import csv

        header = ["name", "initial", "units", "carrier", "ppb", "chem_index", "chem_name"]
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            for state in states:
                w.writerow(
                    [
                        state.get("name", ""),
                        ScenarioIO._format_excel_cell(state.get("initial", "")),
                        state.get("units", ""),
                        ScenarioIO._format_excel_cell(state.get("carrier", "")),
                        ScenarioIO._format_excel_cell(state.get("ppb", "")),
                        ScenarioIO._format_excel_cell(state.get("chem_index", "")),
                        state.get("chem_name", ""),
                    ]
                )

    @staticmethod
    def save_inflow_loadings(
        loadings: list[dict],
        file: str,
    ) -> None:
        if not loadings:
            return
        import csv

        header = [
            "name",
            "mode",
            "date",
            "value",
            "units",
            "mult_ldg",
            "no_user_load",
        ]
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            for record in loadings:
                name = record.get("name", "")
                units = record.get("units", "")
                mult_ldg = ScenarioIO._format_excel_cell(record.get("mult_ldg", ""))
                no_user_load = "TRUE" if record.get("no_user_load") else "FALSE"
                series = record.get("series") or {}
                if series:
                    for t, value in sorted(series.items()):
                        w.writerow(
                            [
                                name,
                                "series",
                                t.strftime("%d.%m.%Y"),
                                ScenarioIO._format_excel_cell(value),
                                units,
                                mult_ldg,
                                no_user_load,
                            ]
                        )
                else:
                    const_value = record.get("const_load", "")
                    mode = "constant" if record.get("use_constant") else "none"
                    w.writerow(
                        [
                            name,
                            mode,
                            "",
                            ScenarioIO._format_excel_cell(const_value),
                            units,
                            mult_ldg,
                            no_user_load,
                        ]
                    )

    @staticmethod
    def save_direct_precip_loadings(
        loadings: list[dict],
        file: str,
    ) -> None:
        if not loadings:
            return
        import csv

        header = [
            "name",
            "mode",
            "date",
            "value",
            "units",
            "mult_ldg",
            "no_user_load",
        ]
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            for record in loadings:
                name = record.get("name", "")
                units = record.get("units", "")
                mult_ldg = ScenarioIO._format_excel_cell(record.get("mult_ldg", ""))
                no_user_load = "TRUE" if record.get("no_user_load") else "FALSE"
                series = record.get("series") or {}
                if series:
                    for t, value in sorted(series.items()):
                        w.writerow(
                            [
                                name,
                                "series",
                                t.strftime("%d.%m.%Y"),
                                ScenarioIO._format_excel_cell(value),
                                units,
                                mult_ldg,
                                no_user_load,
                            ]
                        )
                else:
                    const_value = record.get("const_load", "")
                    mode = "constant" if record.get("use_constant") else "none"
                    w.writerow(
                        [
                            name,
                            mode,
                            "",
                            ScenarioIO._format_excel_cell(const_value),
                            units,
                            mult_ldg,
                            no_user_load,
                        ]
                    )

    @staticmethod
    def save_point_source_loadings(
        loadings: list[dict],
        file: str,
    ) -> None:
        if not loadings:
            return
        import csv

        header = [
            "name",
            "mode",
            "date",
            "value",
            "units",
            "mult_ldg",
            "no_user_load",
        ]
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            for record in loadings:
                name = record.get("name", "")
                units = record.get("units", "")
                mult_ldg = ScenarioIO._format_excel_cell(record.get("mult_ldg", ""))
                no_user_load = "TRUE" if record.get("no_user_load") else "FALSE"
                series = record.get("series") or {}
                if series:
                    for t, value in sorted(series.items()):
                        w.writerow(
                            [
                                name,
                                "series",
                                t.strftime("%d.%m.%Y"),
                                ScenarioIO._format_excel_cell(value),
                                units,
                                mult_ldg,
                                no_user_load,
                            ]
                        )
                else:
                    const_value = record.get("const_load", "")
                    mode = "constant" if record.get("use_constant") else "none"
                    w.writerow(
                        [
                            name,
                            mode,
                            "",
                            ScenarioIO._format_excel_cell(const_value),
                            units,
                            mult_ldg,
                            no_user_load,
                        ]
                    )

    @staticmethod
    def save_nonpoint_source_loadings(
        loadings: list[dict],
        file: str,
    ) -> None:
        if not loadings:
            return
        import csv

        header = [
            "name",
            "mode",
            "date",
            "value",
            "units",
            "mult_ldg",
            "no_user_load",
        ]
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            for record in loadings:
                name = record.get("name", "")
                units = record.get("units", "")
                mult_ldg = ScenarioIO._format_excel_cell(record.get("mult_ldg", ""))
                no_user_load = "TRUE" if record.get("no_user_load") else "FALSE"
                series = record.get("series") or {}
                if series:
                    for t, value in sorted(series.items()):
                        w.writerow(
                            [
                                name,
                                "series",
                                t.strftime("%d.%m.%Y"),
                                ScenarioIO._format_excel_cell(value),
                                units,
                                mult_ldg,
                                no_user_load,
                            ]
                        )
                else:
                    const_value = record.get("const_load", "")
                    mode = "constant" if record.get("use_constant") else "none"
                    w.writerow(
                        [
                            name,
                            mode,
                            "",
                            ScenarioIO._format_excel_cell(const_value),
                            units,
                            mult_ldg,
                            no_user_load,
                        ]
                    )

    @staticmethod
    def save_all_series(
        rows: list[tuple[datetime, dict]],
        file: str,
    ) -> None:
        if not rows:
            return
        import csv

        header = [
            "time",
            "volume_m3",
            "inflow_m3_per_day",
            "outflow_m3_per_day",
            "temp_epi_degC",
            "temp_hypo_degC",
            "wind_m_s",
            "light_ly_d",
            "ph",
            "tss_mg_l",
        ]
        with open(file, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            for t, snapshot in rows:
                w.writerow(
                    [t.strftime("%d.%m.%Y")]
                    + [ScenarioIO._format_excel_cell(snapshot.get(name, "")) for name in header[1:]]
                )

    @staticmethod
    def _format_excel_number(value: float | None) -> str:
        if value is None:
            return ""
        return str(value).replace(".", ",")

    @staticmethod
    def _format_excel_cell(value) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value).replace(".", ",")
        return str(value)

class Utils:
    @staticmethod
    def interpolate_series(series, t):
        # Stage-1: exact lookup (same as Environment); real interpolation later
        return series.get(t, 0.0)

    @staticmethod
    def calc_light_penetration():
        # Placeholder; implemented in later stages
        return 1.0
