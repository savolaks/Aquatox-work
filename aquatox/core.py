# aquatox/core.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import bisect
import math

from .typing_ext import Date

DEFAULT_WIND_CYCLE_DAYS = 365
DEFAULT_WIND_EPOCH_ORDINAL = datetime(2000, 1, 1).toordinal()
DEFAULT_WIND_TERMS: list[tuple[int, float, float]] = [
    (1, 0.83408, 0.87256),
    (2, 0.4245, -0.2871),
    (4, -0.2158, -0.6634),
    (8, -0.0264, -0.2766),
    (16, 0.0236, -0.3492),
    (32, -0.442, 0.89),
    (64, -1.4385, 0.634),
    (128, 0.0935, -1.06),
    (200, -0.564, -0.291),
    (300, -0.6484, 0.6162),
    (6, 0.1083, 0.4047),
    (3, 0.0268, -0.1209),
]

# ---------------------------
# Environment (per UML)
# ---------------------------
@dataclass
class Environment:
    volume: float                 # m^3     <<initial lake volume>>
    area: float                   # m^2     <<surface area>>
    depth_mean: float             # m
    depth_max: float              # m
    inflow_series: Dict[Date, float]   # m^3/day
    outflow_series: Dict[Date, float]  # m^3/day
    temp_epi_series: Dict[Date, float] = field(default_factory=dict)
    temp_hypo_series: Dict[Date, float] = field(default_factory=dict)
    temp_epi_constant: float | None = None
    temp_hypo_constant: float | None = None
    temp_epi_mean: float | None = None
    temp_epi_range: float | None = None
    temp_hypo_mean: float | None = None
    temp_hypo_range: float | None = None
    temp_forcing_mode: str = "series"  # series | series_interpolate | mean_range | constant
    wind_series: Dict[Date, float] = field(default_factory=dict)
    wind_constant: float | None = None
    wind_mean: float | None = None
    wind_forcing_mode: str = "constant"  # constant | default_series | time_varying
    light_series: Dict[Date, float] = field(default_factory=dict)
    light_constant: float | None = None
    light_mean: float | None = None
    light_range: float | None = None
    light_forcing_mode: str = "constant"  # constant | mean_range | time_varying
    food_web: "FoodWeb | None" = None

    def get_inflow(self, t: Date) -> float:
        return self._get_series_value(self.inflow_series, t)

    def get_outflow(self, t: Date) -> float:
        return self._get_series_value(self.outflow_series, t)

    def get_temp_epi(self, t: Date) -> float:
        return self._get_series_value(self.temp_epi_series, t)

    def get_temp_hypo(self, t: Date) -> float:
        return self._get_series_value(self.temp_hypo_series, t)

    def get_temperature_pair(self, t: Date) -> tuple[float | None, float | None, bool]:
        if self.temp_forcing_mode == "series":
            if not self.temp_epi_series:
                return None, None, False
            epi_value = self.temp_epi_series.get(t)
            hypo_value = self.temp_hypo_series.get(t) if self.temp_hypo_series else None
            if epi_value is None:
                return None, None, False
            if self.temp_hypo_series and hypo_value is None:
                return None, None, False
        elif self.temp_forcing_mode == "series_interpolate":
            if not self.temp_epi_series:
                return None, None, False
            epi_value = self._get_series_value_linear(self.temp_epi_series, t)
            if self.temp_hypo_series:
                hypo_value = self._get_series_value_linear(self.temp_hypo_series, t)
                if hypo_value is None:
                    return None, None, False
            else:
                hypo_value = None
            if epi_value is None:
                return None, None, False
        elif self.temp_forcing_mode == "mean_range":
            epi_value = self._seasonal_value(self.temp_epi_mean, self.temp_epi_range, t)
            hypo_value = self._seasonal_value(self.temp_hypo_mean, self.temp_hypo_range, t)
        else:
            epi_value = self.temp_epi_constant
            hypo_value = self.temp_hypo_constant

        if epi_value is None and hypo_value is None:
            return None, None, False
        if epi_value is None:
            epi_value = hypo_value
        if hypo_value is None:
            hypo_value = epi_value

        stratified = abs(epi_value - hypo_value) > 3.0
        if not stratified:
            hypo_value = epi_value
        return epi_value, hypo_value, stratified

    def get_wind(self, t: Date) -> float | None:
        if self.wind_forcing_mode == "default_series":
            return self._default_wind_value(t)
        if self.wind_forcing_mode == "time_varying":
            if not self.wind_series:
                return None
            return self._get_series_value(self.wind_series, t)
        return self.wind_constant

    def get_light(self, t: Date) -> float | None:
        if self.light_forcing_mode == "time_varying":
            if not self.light_series:
                return None
            return self._get_series_value(self.light_series, t)
        if self.light_forcing_mode == "mean_range":
            return self._seasonal_value(self.light_mean, self.light_range, t)
        return self.light_constant

    def _default_wind_value(self, t: Date) -> float | None:
        if self.wind_mean is None:
            return None
        mean_value = self.wind_mean if self.wind_mean > 0 else 3.0
        julian_day = t.timetuple().tm_yday
        base_angle = 2.0 * math.pi * julian_day / DEFAULT_WIND_CYCLE_DAYS
        value = mean_value
        for freq, coef_cos, coef_sin in DEFAULT_WIND_TERMS:
            angle = base_angle * freq
            value += coef_cos * math.cos(angle) + coef_sin * math.sin(angle)
        return max(value, 0.0)

    @staticmethod
    def _get_series_value(series: Dict[Date, float], t: Date) -> float:
        if not series:
            return 0.0
        if t in series:
            return series[t]
        dates = Environment._get_sorted_dates(series)
        if len(dates) == 1:
            return series[dates[0]]
        start = dates[0]
        end = dates[-1]
        if start <= t <= end:
            return Environment._interpolate_linear(series, dates, t)
        target_year = start.year if t < start else end.year
        t_adj = Environment._shift_to_year(t, target_year)
        cycle_dates = [d for d in dates if d.year == target_year] or dates
        if len(cycle_dates) == 1:
            return series[cycle_dates[0]]
        return Environment._interpolate_cyclic(series, cycle_dates, t_adj)

    @staticmethod
    def _get_series_value_linear(series: Dict[Date, float], t: Date) -> float | None:
        if not series:
            return None
        dates = Environment._get_sorted_dates(series)
        if t < dates[0] or t > dates[-1]:
            return None
        if t in series:
            return series[t]
        return Environment._interpolate_linear(series, dates, t)

    @staticmethod
    def _get_sorted_dates(series: Dict[Date, float]) -> List[Date]:
        return sorted(series.keys())

    @staticmethod
    def _shift_to_year(t: Date, year: int) -> Date:
        return Environment._add_years(t, year - t.year)

    @staticmethod
    def _add_years(t: Date, years: int) -> Date:
        target_year = t.year + years
        try:
            return t.replace(year=target_year)
        except ValueError:
            return t.replace(year=target_year, month=2, day=28)

    @staticmethod
    def _interpolate_linear(series: Dict[Date, float], dates: List[Date], t: Date) -> float:
        idx = bisect.bisect_left(dates, t)
        if idx <= 0:
            return series[dates[0]]
        if idx >= len(dates):
            return series[dates[-1]]
        left = dates[idx - 1]
        right = dates[idx]
        left_val = series[left]
        right_val = series[right]
        span_seconds = (right - left).total_seconds()
        if span_seconds <= 0:
            return left_val
        frac = (t - left).total_seconds() / span_seconds
        return left_val + (right_val - left_val) * frac

    @staticmethod
    def _interpolate_cyclic(series: Dict[Date, float], dates: List[Date], t: Date) -> float:
        dates = sorted(dates)
        first = dates[0]
        last = dates[-1]
        if t in series:
            return series[t]
        t_adj = t
        if t_adj < first:
            t_adj = Environment._add_years(t_adj, 1)
        first_plus = Environment._add_years(first, 1)
        extended_dates = dates + [first_plus]
        idx = bisect.bisect_left(extended_dates, t_adj)
        if idx <= 0:
            return series[first]
        if idx >= len(extended_dates):
            return series[first]
        left = extended_dates[idx - 1]
        right = extended_dates[idx]
        left_val = series[left] if left in series else series[first]
        right_val = series[right] if right in series else series[first]
        span_seconds = (right - left).total_seconds()
        if span_seconds <= 0:
            return left_val
        frac = (t_adj - left).total_seconds() / span_seconds
        return left_val + (right_val - left_val) * frac

    @staticmethod
    def _seasonal_value(mean: float | None, temp_range: float | None, t: Date) -> float | None:
        if mean is None or temp_range is None:
            return None
        amplitude = temp_range / 2.0
        day_of_year = t.timetuple().tm_yday
        peak_day = 200
        angle = 2.0 * math.pi * (day_of_year - peak_day) / 365.0
        return mean + amplitude * math.cos(angle)

# ---------------------------
# StateVariable hierarchy (forward ref; real classes in state.py)
# ---------------------------
class StateVariable:
    name: str
    value: float
    units: str
    def rate(self, t: Date, dt: float, env: "Environment", state_vars: List["StateVariable"]) -> float:
        raise NotImplementedError

# ---------------------------
# ODESolver (per UML)
# ---------------------------
@dataclass
class ODESolver:
    method: str = "Euler"  # <<"Euler","RK4", etc.>>

    def integrate(self, state_vars: List[StateVariable], env: Environment, t: Date, dt_days: float) -> None:
        """Update all state_vars in place using the chosen method.
        Stage-1: Euler explicit.
        """
        if self.method != "Euler":
            raise NotImplementedError("Only Euler is implemented in Stage-1.")

        food_web_rates: Dict[str, float] = {}
        if env.food_web is not None:
            food_web_rates = env.food_web.compute_rates(t, dt_days, env, state_vars)

        # Compute all rates with the current state (avoid in-step side effects)
        rates = [
            sv.rate(t, dt_days, env, state_vars) + food_web_rates.get(sv.name, 0.0)
            for sv in state_vars
        ]

        # Euler step: x_{n+1} = x_n + dt * f(x_n, t)
        for sv, r in zip(state_vars, rates):
            sv.value += dt_days * r

# ---------------------------
# Simulation (per UML)
# ---------------------------
@dataclass
class Simulation:
    env: Environment
    state_vars: List[StateVariable]
    solver: ODESolver
    _outputs: List[Tuple[Date, Dict[str, float]]] = field(default_factory=list)

    @classmethod
    def load_scenario(cls, file_path: str, food_web_path: str | None = None) -> "Simulation":
        # Delegated in io_utils.ScenarioIO; left here to match UML signature
        from .io_utils import ScenarioIO
        env, svs = ScenarioIO.load_initial_conditions(file_path, food_web_path=food_web_path)
        solver = ODESolver(method="Euler")
        return cls(env=env, state_vars=svs, solver=solver)

    def run(self, time_end: Date, dt_days: float) -> None:
        """Main loop: update env volume via flows; integrate states."""
        if not self.state_vars:
            return
        # Decide start time from earliest inflow key or now if absent
        if self.env.inflow_series:
            t = min(self.env.inflow_series.keys())
        elif self.env.outflow_series:
            t = min(self.env.outflow_series.keys())
        else:
            t = datetime.utcnow()

        while t < time_end:
            if self.env.temp_forcing_mode in ("series", "series_interpolate", "mean_range", "constant"):
                epi_temp, hypo_temp, stratified = self.env.get_temperature_pair(t)
                if epi_temp is None or hypo_temp is None:
                    raise ValueError(
                        "Temperature forcing requires full coverage; "
                        "provide a complete time series or use mean/range or constant."
                    )
                for sv in self.state_vars:
                    if sv.name.lower() == "temperature":
                        sv.value = epi_temp
                        break
            if self.env.wind_forcing_mode in ("default_series", "time_varying", "constant"):
                wind_value = self.env.get_wind(t)
                if wind_value is None:
                    raise ValueError(
                        "Wind forcing requires full coverage; "
                        "provide a time series, default mean value, or constant."
                    )
                for sv in self.state_vars:
                    if sv.name.lower() == "wind loading":
                        sv.value = wind_value
                        break
            if self.env.light_forcing_mode in ("constant", "mean_range", "time_varying"):
                light_value = self.env.get_light(t)
                if light_value is None:
                    raise ValueError(
                        "Light forcing requires full coverage; "
                        "provide a time series, annual mean/range, or constant."
                    )
                for sv in self.state_vars:
                    if sv.name.lower() == "light":
                        sv.value = light_value
                        break

            # 1) integrate biological/chemical compartments
            self.solver.integrate(self.state_vars, self.env, t, dt_days)

            # 2) update hydrology (simple water balance: m^3)
            inflow = self.env.get_inflow(t)    # m^3/day
            outflow = self.env.get_outflow(t)  # m^3/day
            self.env.volume += (inflow - outflow) * dt_days

            # 3) record outputs
            snapshot = {sv.name: sv.value for sv in self.state_vars}
            if self.env.temp_forcing_mode in ("series", "series_interpolate", "mean_range", "constant"):
                snapshot["Temperature_Epilimnion"] = epi_temp
                snapshot["Temperature_Hypolimnion"] = hypo_temp
                snapshot["Temperature_Stratified"] = stratified
            self._outputs.append((t, snapshot))

            # 4) advance time
            t = t + timedelta(days=dt_days)

    def output_results(self) -> List[Tuple[Date, Dict[str, float]]]:
        return list(self._outputs)


def simulate_water_volume(
    env: Environment,
    time_start: Date | None = None,
    time_end: Date | None = None,
    dt_days: float = 1.0,
) -> List[Tuple[Date, Dict[str, float]]]:
    series_keys = set(env.inflow_series.keys()) | set(env.outflow_series.keys())
    if not series_keys:
        return []

    if time_start is None:
        time_start = min(series_keys)
    if time_end is None:
        time_end = max(series_keys)

    t = time_start
    outputs: List[Tuple[Date, Dict[str, float]]] = []
    while t <= time_end:
        inflow = env.get_inflow(t)
        outflow = env.get_outflow(t)
        env.volume += (inflow - outflow) * dt_days
        outputs.append(
            (
                t,
                {
                    "volume_m3": env.volume,
                    "inflow_m3_per_day": inflow,
                    "outflow_m3_per_day": outflow,
                },
            )
        )
        t = t + timedelta(days=dt_days)
    return outputs
