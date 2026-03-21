"""
Surplus engine module for sdm630_simulator.

Orchestrates surplus power calculation, SOC floor determination,
hysteresis filtering, and forecast consumption.
"""
from __future__ import annotations

import logging
import math  # noqa: F401 – available for Story 2 logic
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

if __package__:
    from . import DEFAULTS  # access to defaults dict

_LOGGER = logging.getLogger(__name__)

SOC_HARD_FLOOR: int = 50

# Cache key constants — map entity roles in sensor cache (used by sensor.py)
CACHE_KEY_SOC               = "soc_percent"
CACHE_KEY_POWER_TO_GRID     = "power_to_grid_w"
CACHE_KEY_PV_PRODUCTION     = "pv_production_w"
CACHE_KEY_POWER_TO_USER     = "power_to_user_w"
CACHE_KEY_BATTERY_DISCHARGE = "battery_discharge_w"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ForecastData:
    """Solar/weather forecast stub — fully implemented in Epic 3."""

    forecast_available: bool = False
    cloud_coverage_avg: float = 50.0
    solar_forecast_kwh_remaining: float | None = None


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
        if __package__:
            from . import DEFAULTS as _DEFAULTS
        else:
            _DEFAULTS = {}  # unit tests supply full config directly

        time_strategy = self.config.get("time_strategy", _DEFAULTS.get("time_strategy", []))
        default_seasonal = _DEFAULTS.get("seasonal_targets", {})
        seasonal_targets = {**default_seasonal, **self.config.get("seasonal_targets", {})}
        month = snapshot.timestamp.month

        for rule in time_strategy:
            if "before" in rule:
                boundary = self._resolve_time_token(rule["before"], snapshot)
                if boundary is None:
                    continue  # token unresolvable — skip, try next rule
                if snapshot.timestamp < boundary:
                    floor = max(int(rule["soc_floor"]), SOC_HARD_FLOOR)
                    return floor
            elif rule.get("default"):
                floor = int(seasonal_targets.get(month, SOC_HARD_FLOOR))
                if floor < SOC_HARD_FLOOR:
                    _LOGGER.warning(
                        "Configured seasonal_target month=%d value=%d below "
                        "SOC_HARD_FLOOR. Clamping.",
                        month, floor,
                    )
                    floor = SOC_HARD_FLOOR
                return floor

        # Defensive fallback — should not occur with well-formed config
        return SOC_HARD_FLOOR

    def _resolve_time_token(
        self, token: str, snapshot: SensorSnapshot
    ) -> datetime | None:
        """Parse time tokens like 'sunrise+2h', 'sunset-3h', or 'HH:MM'."""
        m = re.match(r"^(sunrise|sunset)([+-])(\d+(?:\.\d+)?)h$", token)
        if m:
            base_name, sign, hours = m.group(1), m.group(2), float(m.group(3))
            base = snapshot.sunrise_time if base_name == "sunrise" else snapshot.sunset_time
            if base is None:
                return None
            delta = timedelta(hours=hours)
            return base + delta if sign == "+" else base - delta
        # Plain "HH:MM" static time
        try:
            t = datetime.strptime(token, "%H:%M").time()
            ts = snapshot.timestamp
            return ts.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        except ValueError:
            _LOGGER.warning("SDM630: Cannot parse time token '%s'", token)
            return None

    def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult:
        """Calculate net surplus adjusted for battery buffer. (Story 2.2)"""
        soc_floor = self.get_soc_floor(snapshot)

        real_surplus_kw = (snapshot.pv_production_w - snapshot.power_to_user_w) / 1000.0

        battery_capacity_kwh = self.config.get("battery_capacity_kwh", 10.0)
        max_discharge_kw     = self.config.get("max_discharge_kw", 10.0)
        hold_time_minutes    = max(self.config.get("hold_time_minutes", 10), 1)  # guard /0
        wallbox_threshold_kw = self.config.get("wallbox_threshold_kw", 4.2)

        soc_headroom      = max(0.0, snapshot.soc_percent - soc_floor)
        buffer_energy_kwh = soc_headroom * battery_capacity_kwh / 100.0
        buffer_kw_max     = min(max_discharge_kw,
                                buffer_energy_kwh / (hold_time_minutes / 60.0))
        buffer_used_kw    = min(buffer_kw_max,
                                max(0.0, wallbox_threshold_kw - real_surplus_kw))
        augmented_kw      = real_surplus_kw + buffer_used_kw

        forecast_available = (
            snapshot.forecast.forecast_available if snapshot.forecast else False
        )

        if augmented_kw >= wallbox_threshold_kw:
            _LOGGER.debug(
                "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
                "state=%s reported=%.2fkW reason=%s forecast=%s",
                real_surplus_kw, buffer_used_kw, snapshot.soc_percent,
                soc_floor, "ACTIVE", augmented_kw,
                "wallbox_included_in_load", forecast_available,
            )
            return EvaluationResult(
                reported_kw       = augmented_kw,
                real_surplus_kw   = real_surplus_kw,
                buffer_used_kw    = buffer_used_kw,
                soc_percent       = snapshot.soc_percent,
                soc_floor_active  = soc_floor,
                charging_state    = "ACTIVE",
                reason            = "wallbox_included_in_load",
                forecast_available = forecast_available,
            )

        _LOGGER.debug(
            "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
            "state=%s reported=%.2fkW reason=%s forecast=%s",
            real_surplus_kw, 0.0, snapshot.soc_percent,
            soc_floor, "INACTIVE", 0.0,
            "surplus_below_threshold", forecast_available,
        )
        return EvaluationResult(
            reported_kw       = 0.0,
            real_surplus_kw   = real_surplus_kw,
            buffer_used_kw    = 0.0,
            soc_percent       = snapshot.soc_percent,
            soc_floor_active  = soc_floor,
            charging_state    = "INACTIVE",
            reason            = "surplus_below_threshold",
            forecast_available = forecast_available,
        )


# ---------------------------------------------------------------------------
# HA-aware classes
# ---------------------------------------------------------------------------

class HysteresisFilter:
    """ACTIVE/INACTIVE/FAILSAFE state machine for wallbox charge signal stabilisation.

    HA-free: only stdlib datetime — fully unit-testable without HA runtime.
    """

    def __init__(self, config: dict) -> None:
        self._state: str = "INACTIVE"
        self._hold_until: datetime | None = None
        self._last_reported_kw: float = 0.0
        self._hold_time_minutes: int = config.get("hold_time_minutes", 10)
        self._wallbox_threshold_kw: float = config.get("wallbox_threshold_kw", 4.2)

    @property
    def state(self) -> str:
        return self._state

    def update(self, reported_kw: float, now: datetime) -> float:
        """Apply hysteresis and return filtered surplus kW. (Story 2.3)"""
        if self._state == "FAILSAFE":
            return 0.0

        if self._state == "INACTIVE":
            if reported_kw >= self._wallbox_threshold_kw:
                self._state = "ACTIVE"
                self._hold_until = now + timedelta(minutes=self._hold_time_minutes)
                self._last_reported_kw = reported_kw
                return reported_kw
            return 0.0

        # ACTIVE branch
        if reported_kw >= self._wallbox_threshold_kw:
            # Renew hold
            self._hold_until = now + timedelta(minutes=self._hold_time_minutes)
            self._last_reported_kw = reported_kw
            return reported_kw

        # Below threshold: check hold
        if self._hold_until is not None and now < self._hold_until:
            # Still within hold period — return last valid value
            return self._last_reported_kw

        # Hold expired
        self._state = "INACTIVE"
        self._hold_until = None
        return 0.0

    def force_failsafe(self, reason: str) -> None:
        """Immediately enter FAILSAFE state. (Story 2.3 / Story 4.x)"""
        _LOGGER.warning("SDM630 HysteresisFilter → FAILSAFE: %s", reason)
        self._state = "FAILSAFE"
        self._hold_until = None
        self._last_reported_kw = 0.0

    def resume(self) -> None:
        """Exit FAILSAFE → INACTIVE. Call only after all sensors confirmed healthy."""
        self._state = "INACTIVE"


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
        self._calculator = SurplusCalculator(config)
        self._hysteresis = HysteresisFilter(config)

    async def evaluate_cycle(self, snapshot: SensorSnapshot) -> EvaluationResult:
        """Run one evaluation cycle and return result."""
        # 1. Pure calculation (Stories 2.1 + 2.2)
        calc = self._calculator.calculate_surplus(snapshot)

        # 2. Apply hysteresis filter (Story 2.3)
        final_kw = self._hysteresis.update(calc.reported_kw, snapshot.timestamp)

        # 3. Determine reason and charging state
        charging_state = self._hysteresis.state
        if charging_state == "FAILSAFE":
            reason = "failsafe_active"
            final_kw = 0.0
        elif final_kw > 0.0:
            reason = calc.reason
        else:
            reason = "hysteresis_hold_or_inactive"

        return EvaluationResult(
            reported_kw=final_kw,
            real_surplus_kw=calc.real_surplus_kw,
            buffer_used_kw=calc.buffer_used_kw,
            soc_percent=calc.soc_percent,
            soc_floor_active=calc.soc_floor_active,
            charging_state=charging_state,
            reason=reason,
            forecast_available=calc.forecast_available,
        )
