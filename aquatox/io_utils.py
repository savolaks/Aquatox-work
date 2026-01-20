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
        temp_forcing_mode = ScenarioIO._choose_temperature_mode(
            temp_epi_series,
            temp_hypo_series,
            temp_epi_mean,
            temp_epi_range,
            temp_hypo_mean,
            temp_hypo_range,
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
