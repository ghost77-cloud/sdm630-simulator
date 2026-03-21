"""
Surplus engine module for sdm630_simulator.

Orchestrates surplus power calculation, SOC floor determination,
hysteresis filtering, and forecast consumption.
"""
from __future__ import annotations

import logging
import math  # noqa: F401 – available for Story 2 logic
from dataclasses import dataclass
from datetime import datetime

if __package__:
    pass  # HA-specific imports will be added in Story 1.3 onward

_LOGGER = logging.getLogger(__name__)

SOC_HARD_FLOOR: int = 50


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ForecastData:
    """Solar/weather forecast stub — fully implemented in Epic 3."""

    forecast_available: bool = False
    cloud_coverage_avg: float = 50.0
    solar_forecast_kwh_today: float | None = None


@dataclass
class SensorSnapshot:
    """Point-in-time reading of all relevant HA sensors."""

    soc_percent: float
    power_to_grid_w: float
    pv_production_w: float
    power_to_user_w: float
    timestamp: datetime
    sunset_time: datetime | None
    sunrise_time: datetime | None
    forecast: ForecastData | None = None


@dataclass
class EvaluationResult:
    """Output of a single surplus evaluation cycle."""

    reported_kw: float
    real_surplus_kw: float
    buffer_used_kw: float
    soc_percent: float
    soc_floor_active: int
    charging_state: str        # "ACTIVE" | "INACTIVE" | "FAILSAFE"
    reason: str                # human-readable one-liner for log
    forecast_available: bool


# ---------------------------------------------------------------------------
# Pure-logic class (stdlib only, zero HA imports)
# ---------------------------------------------------------------------------

class SurplusCalculator:
    """Calculates surplus power and SOC floor — no HA dependencies."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def get_soc_floor(self, snapshot: SensorSnapshot) -> int:
        """Return current SOC floor based on time-window strategy. (Story 2.1)"""
        raise NotImplementedError

    def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult:
        """Calculate net surplus adjusted for battery buffer. (Story 2.2)"""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# HA-aware classes
# ---------------------------------------------------------------------------

class HysteresisFilter:
    """Applies hold-time hysteresis to the surplus signal. (Story 2.3)"""

    def __init__(self, hold_time_minutes: int) -> None:
        pass

    def update(self, reported_kw: float, now: datetime) -> float:
        """Apply hysteresis and return filtered surplus. (Story 2.3)"""
        raise NotImplementedError

    def force_failsafe(self, reason: str) -> None:
        """Immediately enter FAILSAFE state. (Story 4.x)"""
        raise NotImplementedError

    def resume(self) -> None:
        """Exit FAILSAFE and return to normal evaluation. (Story 4.x)"""
        raise NotImplementedError


class ForecastConsumer:
    """Fetches and caches solar/weather forecasts from HA. (Story 3.1)"""

    def __init__(self, config: dict) -> None:
        self.config = config

    async def get_forecast(self, hass) -> ForecastData:
        """Fetch forecast from HA weather entity. (Story 3.1)"""
        raise NotImplementedError


class SurplusEngine:
    """Orchestrator — coordinates all sub-components each evaluation cycle."""

    def __init__(self, config: dict) -> None:
        self.config = config

    async def evaluate_cycle(self, snapshot: SensorSnapshot) -> EvaluationResult:
        """Run one evaluation cycle and return result.

        Returns a safe default EvaluationResult until Story 2 implements
        real logic. Must be ``async def`` — Story 3 will await get_forecast.
        """
        return EvaluationResult(
            reported_kw=0.0,
            real_surplus_kw=0.0,
            buffer_used_kw=0.0,
            soc_percent=0.0,
            soc_floor_active=50,
            charging_state="INACTIVE",
            reason="engine_not_yet_implemented",
            forecast_available=False,
        )
