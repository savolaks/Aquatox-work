# aquatox/foodweb.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import re

from .typing_ext import Date
from .state import Animal, Biota


@dataclass(frozen=True)
class FoodWebInteraction:
    predator: str
    prey: str
    observations: int
    params: Sequence[Optional[float]]
    diet_percent: Optional[float]
    habitat_code: Optional[int]


@dataclass
class FoodWeb:
    interactions: List[FoodWebInteraction]
    default_assimilation: float = 0.7
    preference_source: str = "diet_percent"
    _predator_index: Dict[str, List[FoodWebInteraction]] = field(default_factory=dict, init=False)
    _predator_index_norm: Dict[str, List[FoodWebInteraction]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for interaction in self.interactions:
            self._predator_index.setdefault(interaction.predator, []).append(interaction)
            norm = _normalize_name(interaction.predator)
            self._predator_index_norm.setdefault(norm, []).append(interaction)

    @classmethod
    def from_interspecies_csv(cls, path: str) -> "FoodWeb":
        import csv

        interactions: List[FoodWebInteraction] = []
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row or len(row) < 3:
                    continue
                predator = row[0].strip()
                prey = row[1].strip()
                observations = _parse_int(row[2])
                params = [_parse_float(token) for token in row[3:18]]
                diet_percent = _parse_float(row[18]) if len(row) > 18 else None
                habitat_code = _parse_int(row[19]) if len(row) > 19 else None
                interactions.append(
                    FoodWebInteraction(
                        predator=predator,
                        prey=prey,
                        observations=observations,
                        params=params,
                        diet_percent=diet_percent,
                        habitat_code=habitat_code,
                    )
                )
        return cls(interactions=interactions)

    def compute_rates(
        self,
        t: Date,
        dt_days: float,
        env,
        state_vars: Iterable,
    ) -> Dict[str, float]:
        del t, dt_days, env
        rates: Dict[str, float] = {}
        by_name = {sv.name: sv for sv in state_vars}
        by_norm = {_normalize_name(sv.name): sv for sv in state_vars}

        for predator_name, interactions in self._predator_index.items():
            predator = by_name.get(predator_name)
            if predator is None:
                predator = by_norm.get(_normalize_name(predator_name))
            if predator is None:
                continue
            consumption_rate = getattr(predator, "consumption_rate", 0.0)
            if consumption_rate <= 0.0:
                continue

            preferences = getattr(predator, "feeding_prefs", {}) or {}
            weights = _build_weights(
                interactions=interactions,
                preferences=preferences,
                preference_source=self.preference_source,
            )
            if not weights:
                continue

            weighted_prey = []
            total_weight = 0.0
            for prey_name, weight in weights.items():
                prey = by_name.get(prey_name)
                if prey is None:
                    prey = by_norm.get(_normalize_name(prey_name))
                if prey is None or weight <= 0.0:
                    continue
                availability = max(prey.value, 0.0)
                if availability <= 0.0:
                    continue
                scaled = weight * availability
                weighted_prey.append((prey, scaled))
                total_weight += scaled
            if total_weight <= 0.0:
                continue

            ingestion = consumption_rate * max(predator.value, 0.0)
            if ingestion <= 0.0:
                continue

            assimilation_eff = getattr(predator, "assimilation_eff", self.default_assimilation)
            predator_gain = 0.0
            for prey, scaled in weighted_prey:
                fraction = scaled / total_weight
                consumed = ingestion * fraction
                consumed = min(consumed, max(prey.value, 0.0))
                if consumed <= 0.0:
                    continue
                rates[prey.name] = rates.get(prey.name, 0.0) - consumed
                predator_gain += consumed

            if predator_gain > 0.0:
                rates[predator.name] = rates.get(predator.name, 0.0) + predator_gain * assimilation_eff

        return rates

    def build_foodweb_matrices(
        self,
        state_vars: Iterable,
    ) -> Tuple[List[str], List[List[Optional[float]]], List[List[Optional[float]]]]:
        organisms = [sv for sv in state_vars if isinstance(sv, Biota)]
        names = [sv.name for sv in organisms]
        name_set = set(names)
        name_by_obj = {sv.name: sv for sv in organisms}
        index_by_name = {name: idx for idx, name in enumerate(names)}
        name_by_norm = {_normalize_name(name): name for name in names}

        preferences: List[List[Optional[float]]] = [
            [None for _ in names] for _ in names
        ]
        egestion: List[List[Optional[float]]] = [
            [None for _ in names] for _ in names
        ]

        for predator_name in names:
            interactions = self._predator_index.get(predator_name, [])
            if not interactions:
                interactions = self._predator_index_norm.get(_normalize_name(predator_name), [])
            predator = name_by_obj[predator_name]
            preferences_map = getattr(predator, "feeding_prefs", {}) or {}
            weights = _build_weights(
                interactions=interactions,
                preferences=preferences_map,
                preference_source=self.preference_source,
            )
            if not weights:
                continue
            assimilation_eff = getattr(predator, "assimilation_eff", self.default_assimilation)
            egestion_coeff = 1.0 - max(0.0, min(assimilation_eff, 1.0))
            row_idx = index_by_name[predator_name]
            for prey_name, weight in weights.items():
                target_prey = prey_name if prey_name in name_set else name_by_norm.get(_normalize_name(prey_name))
                if not target_prey:
                    continue
                col_idx = index_by_name[target_prey]
                preferences[row_idx][col_idx] = weight
                egestion[row_idx][col_idx] = egestion_coeff

        return names, preferences, egestion


def _build_weights(
    interactions: Iterable[FoodWebInteraction],
    preferences: Dict[str, float],
    preference_source: str,
) -> Dict[str, float]:
    if preferences:
        return {prey: weight for prey, weight in preferences.items() if weight is not None}

    weights: Dict[str, float] = {}
    for interaction in interactions:
        weight = None
        if preference_source == "diet_percent":
            weight = interaction.diet_percent
        elif preference_source == "observations":
            weight = float(interaction.observations)
        else:
            weight = interaction.diet_percent if interaction.diet_percent is not None else float(interaction.observations)
        if weight is None:
            continue
        weights[interaction.prey] = weight
    return weights


def _parse_float(raw: str) -> Optional[float]:
    token = raw.strip()
    if not token or token.lower() in ("na", "nan"):
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _parse_int(raw: str) -> int:
    token = raw.strip()
    if not token or token.lower() in ("na", "nan"):
        return 0
    try:
        return int(float(token))
    except ValueError:
        return 0


def _normalize_name(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[()]", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()
