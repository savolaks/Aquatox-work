# aquatox/io_utils.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
from typing import Dict, List, Tuple

from .core import Environment
from .state import StateVariable, Nutrient, Detritus, Plant, Animal, Biota

class ScenarioIO:
    @staticmethod
    def load_initial_conditions(file: str) -> tuple[Environment, list[StateVariable]]:
        """Load a scenario file or fall back to a tiny synthetic scenario."""
        path = Path(file)
        if not path.exists():
            return ScenarioIO._load_synthetic()

        text = path.read_text(encoding="utf-8", errors="ignore")
        env = ScenarioIO._parse_environment(text)
        state_vars = ScenarioIO._parse_state_variables(text)
        if not state_vars:
            state_vars = ScenarioIO._default_state_vars()
        return env, state_vars

    @staticmethod
    def _load_synthetic() -> tuple[Environment, list[StateVariable]]:
        t0 = datetime(1992, 1, 1)
        inflow_series = {t0 + timedelta(days=i): 10.0 for i in range(10)}
        outflow_series = {t0 + timedelta(days=i): 10.0 for i in range(10)}
        env = Environment(
            volume=1_000.0,
            area=1_000.0,
            depth_mean=5.4,
            depth_max=25.0,
            inflow_series=inflow_series,
            outflow_series=outflow_series,
        )
        return env, ScenarioIO._default_state_vars()

    @staticmethod
    def _default_state_vars() -> list[StateVariable]:
        nitrate = Nutrient(name="Nitrate", value=0.4, units="mg/L", form="NO3")
        return [nitrate]

    @staticmethod
    def _parse_environment(text: str) -> Environment:
        volume = ScenarioIO._find_float(text, r'"StaticVolume":\s*([-\d.E+]+)') or 1_000.0
        area = ScenarioIO._find_float(text, r'"SurfArea":\s*([-\d.E+]+)') or 1_000.0
        depth_mean = ScenarioIO._find_float(text, r'"ICZMean":\s*([-\d.E+]+)') or 5.4
        depth_max = ScenarioIO._find_float(text, r'"ZMax":\s*([-\d.E+]+)') or 25.0

        inflow_series = ScenarioIO._parse_inflow_series(text)
        if inflow_series:
            mean_inflow = sum(inflow_series.values()) / len(inflow_series)
            outflow_series = {t: mean_inflow for t in inflow_series}
        else:
            t0 = datetime(1992, 1, 1)
            inflow_series = {t0 + timedelta(days=i): 0.0 for i in range(10)}
            outflow_series = {t0 + timedelta(days=i): 0.0 for i in range(10)}

        return Environment(
            volume=volume,
            area=area,
            depth_mean=depth_mean,
            depth_max=depth_max,
            inflow_series=inflow_series,
            outflow_series=outflow_series,
        )

    @staticmethod
    def _parse_inflow_series(text: str) -> Dict[datetime, float]:
        blocks = ScenarioIO._extract_state_blocks(text)
        for block in blocks:
            if ScenarioIO._find_str(block, r'"PName\^":\s*"([^"]+)"') != "Water Volume":
                continue
            series_line = ScenarioIO._find_str(
                block, r"Alt\. Time Series Loadings:\s*n=\d+;([^\\n]+)"
            )
            if not series_line:
                continue
            return ScenarioIO._parse_time_series(series_line)
        return {}

    @staticmethod
    def _parse_state_variables(text: str) -> list[StateVariable]:
        state_vars: list[StateVariable] = []
        for record in ScenarioIO._parse_state_records(text):
            state_vars.append(ScenarioIO._make_state_var(record))
        return state_vars

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
            try:
                timestamp = datetime.strptime(date_text, "%d/%m/%Y")
                value = float(value_text)
            except ValueError:
                continue
            series[timestamp] = value
        return series

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
            w = csv.writer(f)
            w.writerow(["time"] + names)
            for t, snapshot in results:
                w.writerow([t.isoformat()] + [snapshot.get(n, "") for n in names])

class Utils:
    @staticmethod
    def interpolate_series(series, t):
        # Stage-1: exact lookup (same as Environment); real interpolation later
        return series.get(t, 0.0)

    @staticmethod
    def calc_light_penetration():
        # Placeholder; implemented in later stages
        return 1.0
