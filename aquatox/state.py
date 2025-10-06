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
    """Concrete base class wiring dataclass behaviour onto the UML stub.

    The derived classes override :meth:`rate` to encode the differential
    equations relevant to each compartment.  The Stage-1 placeholder leaves the
    method as a no-op so that the integration stack can be exercised without a
    fully specified biogeochemical model.
    """
    name: str
    value: float        # current mass/conc
    units: str

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        """Return the instantaneous change rate (defaulting to a no-op)."""
        # Abstract in UML; default no change for base
        return 0.0

# ---------------------------
# Nutrient (per UML)
# ---------------------------
@dataclass
class Nutrient(StateVariable):
    """Represent dissolved nutrient pools such as nitrogen or phosphorus.

    Additional metadata describing the chemical ``form`` is stored to make it
    straightforward to connect uptake and remineralisation pathways later in
    the project.
    """
    form: str  # e.g. "NH4","NO3","PO4","O2","CO2"

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        """Return zero while Stage-1 omits transformation pathways."""
        # Stage-1 placeholder: no internal reactions; external processes will come later
        # Keep zero so tests can assert stability.
        return 0.0

# ---------------------------
# Detritus (per UML)
# ---------------------------
@dataclass
class Detritus(StateVariable):
    """Track particulate organic matter pools awaiting decomposition logic.

    Attributes capture the particulate ``type`` (labile vs. refractory) and the
    environmental ``layer`` (water column vs. sediment) so that future kinetics
    can quickly branch on the appropriate process representation.
    """
    type: str   # "labile" | "refractory"
    layer: str  # "water" | "sediment"

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        """Keep detrital stocks constant until decay/settling is implemented."""
        # Stage-1 placeholder: no decay/settling yet
        return 0.0

# ---------------------------
# Biota + Plant + Animal (per UML)
# ---------------------------
@dataclass
class Biota(StateVariable):
    """Base class for living compartments with simple growth and mortality.

    AQUATOX typically tracks biomass rather than concentration for organisms.
    The ``value`` attribute therefore mirrors ``biomass`` to stay compatible
    with the solver interface, while storing explicit growth and mortality
    coefficients keeps the intent readable.
    """
    biomass: float           # alias to value (kept separately for clarity)
    max_growth: float        # per day (Stage-1 placeholder)
    mortality_rate: float    # per day

    def __post_init__(self):
        """Ensure the ``value`` attribute mirrors the provided biomass."""
        # Keep value and biomass in sync
        self.value = self.biomass

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        """Compute net biomass change from constant growth and mortality terms."""
        # Stage-1: simple net = growth - mortality (no interactions yet)
        growth = self.max_growth * self.value
        loss = self.mortality_rate * self.value
        return growth - loss

@dataclass
class Plant(Biota):
    """Autotrophic biota placeholder that will couple to nutrients later."""
    nutrient_uptake_rate: float  # placeholder, used in later stages

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        """Defer to :class:`Biota` until nutrient feedback is introduced."""
        # Stage-1: same as Biota (no nutrient coupling yet)
        return super().rate(t, dt, env, state_vars)

@dataclass
class Animal(Biota):
    """Heterotrophic biota placeholder pending consumption dynamics.

    Diet composition (``feeding_prefs``) and ``consumption_rate`` are stored so
    that the trophic interactions can be implemented by modifying the rate
    method without needing to revisit the scenario input schema.
    """
    feeding_prefs: Dict[str, float]  # diet composition by state name
    consumption_rate: float

    def rate(self, t: Date, dt: float, env: Environment, state_vars: List["StateVariable"]) -> float:
        """Reuse :class:`Biota` growth/mortality until trophic links are added."""
        # Stage-1: same as Biota; consumption wiring will arrive in Stage-2/3
        return super().rate(t, dt, env, state_vars)
