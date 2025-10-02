# aquatox/state.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime as Date

from .core import Environment, StateVariable as _StateVariableBase

# ---------------------------
# Base StateVariable (per UML)
# ---------------------------
@dataclass
class StateVariable(_StateVariableBase):
    name: str
    value: float        # current mass/conc
    units: str

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        # Abstract in UML; default no change for base
        return 0.0

# ---------------------------
# Nutrient (per UML)
# ---------------------------
@dataclass
class Nutrient(StateVariable):
    form: str  # e.g. "NH4","NO3","PO4","O2","CO2"

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        # Stage-1 placeholder: no internal reactions; external processes will come later
        # Keep zero so tests can assert stability.
        return 0.0

# ---------------------------
# Detritus (per UML)
# ---------------------------
@dataclass
class Detritus(StateVariable):
    type: str   # "labile" | "refractory"
    layer: str  # "water" | "sediment"

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        # Stage-1 placeholder: no decay/settling yet
        return 0.0

# ---------------------------
# Biota + Plant + Animal (per UML)
# ---------------------------
@dataclass
class Biota(StateVariable):
    biomass: float           # alias to value (kept separately for clarity)
    max_growth: float        # per day (Stage-1 placeholder)
    mortality_rate: float    # per day

    def __post_init__(self):
        # Keep value and biomass in sync
        self.value = self.biomass

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        # Stage-1: simple net = growth - mortality (no interactions yet)
        growth = self.max_growth * self.value
        loss = self.mortality_rate * self.value
        return growth - loss

@dataclass
class Plant(Biota):
    nutrient_uptake_rate: float  # placeholder, used in later stages

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        # Stage-1: same as Biota (no nutrient coupling yet)
        return super().rate(t, dt, env, state_vars)

@dataclass
class Animal(Biota):
    feeding_prefs: Dict[str, float]  # diet composition by state name
    consumption_rate: float

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        # Stage-1: same as Biota; consumption wiring will arrive in Stage-2/3
        return super().rate(t, dt, env, state_vars)
