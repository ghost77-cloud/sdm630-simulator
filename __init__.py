"""
Home Assistant custom component to simulate an Eastron SDM630 smart meter.
"""
import logging
import os
import sys

import voluptuous as vol

DOMAIN = "sdm630_simulator"

# Standalone import guard — enables `python __init__.py` without HA
if __package__ is None:
    DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, DIR)

# ── Logging ───────────────────────────────────────────────────────────────────
_LOGGER = logging.getLogger(__name__)

# ── HA config_validation with standalone fallback ─────────────────────────────
try:
    import homeassistant.helpers.config_validation as cv
except ImportError:
    # Standalone mode: minimal entity_id stub
    class _cv:  # noqa: N801
        @staticmethod
        def entity_id(value: str) -> str:
            if not isinstance(value, str) or "." not in value:
                raise vol.Invalid(f"Invalid entity_id: {value!r}")
            return value

    cv = _cv()  # type: ignore[assignment]

# ── Config key constants ──────────────────────────────────────────────────────
CONF_ENTITIES             = "entities"
CONF_SOC                  = "soc"              # required
CONF_POWER_TO_GRID        = "power_to_grid"    # required
CONF_PV_PRODUCTION        = "pv_production"    # required
CONF_POWER_TO_USER        = "power_to_user"    # required
CONF_WEATHER              = "weather"          # optional
CONF_FORECAST_SOLAR       = "forecast_solar"   # optional

CONF_TIME_STRATEGY        = "time_strategy"
CONF_SEASONAL_TARGETS     = "seasonal_targets"
CONF_EVALUATION_INTERVAL  = "evaluation_interval"
CONF_WALLBOX_THRESHOLD_KW = "wallbox_threshold_kw"
CONF_WALLBOX_MIN_KW       = "wallbox_min_kw"
CONF_HOLD_TIME_MINUTES    = "hold_time_minutes"
CONF_SOC_HARD_FLOOR       = "soc_hard_floor"
CONF_STALE_THRESHOLD_SECONDS = "stale_threshold_seconds"
CONF_MAX_DISCHARGE_KW     = "max_discharge_kw"
CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"
CONF_SOLAR_REMAINING_THRESHOLD_KWH = "solar_remaining_threshold_kwh"
CONF_MAX_INVERTER_OUTPUT_KW = "max_inverter_output_kw"
CONF_SENSOR_RANGES        = "sensor_ranges"   # optional; keys: soc, power_w

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULTS: dict = {
    "evaluation_interval": 15,
    "wallbox_threshold_kw": 4.2,
    "wallbox_min_kw": 4.1,
    "hold_time_minutes": 10,
    "soc_hard_floor": 50,
    "stale_threshold_seconds": 60,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "max_inverter_output_kw": 10.0,
    "solar_remaining_threshold_kwh": 2.0,
    # sensor_ranges: plausible value bounds for cache validation (Story 4.4)
    # Override in YAML with sensor_ranges: { soc: [0, 100], power_w: [-30000, 30000] }
    "sensor_ranges": {
        "soc": (0, 100),          # SOC % — always 0–100
        "power_w": (-30000, 30000),  # W — bidirectional (grid export = negative)
    },
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70,  8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},  # morning protection
        {"before": "sunset-3h",  "soc_floor": 50},   # free midday window
        {"default": True,        "soc_floor": 80},   # evening / seasonal
    ],
}

# ── Voluptuous schemas ────────────────────────────────────────────────────────

ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SOC):           cv.entity_id,
        vol.Required(CONF_POWER_TO_GRID): cv.entity_id,
        vol.Required(CONF_PV_PRODUCTION): cv.entity_id,
        vol.Required(CONF_POWER_TO_USER): cv.entity_id,
        vol.Optional(CONF_WEATHER):       cv.entity_id,
        vol.Optional(CONF_FORECAST_SOLAR): cv.entity_id,
    }
)

TIME_ENTRY_SCHEMA = vol.Any(
    vol.Schema({"before": str,    "soc_floor": vol.All(int, vol.Range(0, 100))}),
    vol.Schema({"default": True,  "soc_floor": vol.All(int, vol.Range(0, 100))}),
)

TIME_STRATEGY_SCHEMA = [TIME_ENTRY_SCHEMA]

SEASONAL_TARGETS_SCHEMA = vol.Schema(
    {vol.All(vol.Coerce(int), vol.Range(min=1, max=12)): vol.All(int, vol.Range(min=0, max=100))}
)

def _validate_range_order(pair):
    """Reject inverted ranges where min > max."""
    if pair[0] > pair[1]:
        raise vol.Invalid(f"min must be \u2264 max, got {pair}")
    return pair

SENSOR_RANGE_PAIR = vol.All(
    [vol.Coerce(float)],
    vol.Length(min=2, max=2),
    _validate_range_order,
)
SENSOR_RANGES_SCHEMA = vol.Schema(
    {
        vol.Optional("soc"):     SENSOR_RANGE_PAIR,
        vol.Optional("power_w"): SENSOR_RANGE_PAIR,
    }
)

COMPONENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITIES):              ENTITIES_SCHEMA,
        vol.Optional(CONF_TIME_STRATEGY):         TIME_STRATEGY_SCHEMA,
        vol.Optional(CONF_SEASONAL_TARGETS):      SEASONAL_TARGETS_SCHEMA,
        vol.Optional(CONF_EVALUATION_INTERVAL):   int,
        vol.Optional(CONF_WALLBOX_THRESHOLD_KW):  vol.Coerce(float),
        vol.Optional(CONF_WALLBOX_MIN_KW):        vol.Coerce(float),
        vol.Optional(CONF_HOLD_TIME_MINUTES):     int,
        vol.Optional(CONF_SOC_HARD_FLOOR):        vol.All(int, vol.Range(0, 100)),
        vol.Optional(CONF_STALE_THRESHOLD_SECONDS): int,
        vol.Optional(CONF_MAX_DISCHARGE_KW):      vol.Coerce(float),
        vol.Optional(CONF_BATTERY_CAPACITY_KWH):  vol.Coerce(float),
        vol.Optional(CONF_MAX_INVERTER_OUTPUT_KW): vol.Coerce(float),
        vol.Optional(CONF_SOLAR_REMAINING_THRESHOLD_KWH): vol.Coerce(float),
        vol.Optional(CONF_SENSOR_RANGES):          SENSOR_RANGES_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: COMPONENT_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


# ── Component setup ───────────────────────────────────────────────────────────

async def async_setup(hass, config):
    """Set up the SDM630 simulator component."""
    raw_cfg: dict = config.get(DOMAIN, {})

    # -- Apply scalar DEFAULTS (skip nested dicts handled separately below) --
    _SCALAR_KEYS = {
        "evaluation_interval", "wallbox_threshold_kw", "wallbox_min_kw",
        "hold_time_minutes", "soc_hard_floor", "stale_threshold_seconds",
        "max_discharge_kw", "battery_capacity_kwh", "max_inverter_output_kw",
        "solar_remaining_threshold_kwh",
    }
    cfg: dict = {}
    for key in _SCALAR_KEYS:
        cfg[key] = raw_cfg.get(key, DEFAULTS[key])

    # -- Merge seasonal_targets: user entries override defaults per month --
    merged_seasonal: dict = dict(DEFAULTS["seasonal_targets"])
    if CONF_SEASONAL_TARGETS in raw_cfg:
        merged_seasonal.update(raw_cfg[CONF_SEASONAL_TARGETS])
    cfg[CONF_SEASONAL_TARGETS] = merged_seasonal

    # -- time_strategy: user list overrides default entirely --
    cfg[CONF_TIME_STRATEGY] = raw_cfg.get(CONF_TIME_STRATEGY, DEFAULTS["time_strategy"])

    # -- sensor_ranges: optional; validate sub-keys present; fall back per missing key --
    raw_ranges = raw_cfg.get(CONF_SENSOR_RANGES, {})
    default_ranges = DEFAULTS["sensor_ranges"]
    sensor_ranges: dict = {}
    for sub_key in ("soc", "power_w"):
        if sub_key in raw_ranges:
            val = raw_ranges[sub_key]
            sensor_ranges[sub_key] = tuple(val) if isinstance(val, list) else val
        else:
            if raw_ranges:  # user supplied partial sensor_ranges block
                _LOGGER.warning(
                    "%s: sensor_ranges.%s missing \u2014 using default %s",
                    DOMAIN,
                    sub_key,
                    default_ranges[sub_key],
                )
            sensor_ranges[sub_key] = default_ranges[sub_key]
    cfg[CONF_SENSOR_RANGES] = sensor_ranges

    # -- Entities: required / optional validation --
    entities_cfg: dict = raw_cfg.get(CONF_ENTITIES, {})

    if CONF_SOC not in entities_cfg:
        _LOGGER.error(
            "%s: required entity 'soc' missing — entering FAILSAFE mode",
            DOMAIN,
        )
        cfg["failsafe"] = True
    else:
        cfg["failsafe"] = False

    for optional_key in (CONF_WEATHER, CONF_FORECAST_SOLAR):
        if optional_key not in entities_cfg:
            _LOGGER.warning(
                "%s: optional entity '%s' not configured — degraded mode",
                DOMAIN,
                optional_key,
            )

    cfg[CONF_ENTITIES] = entities_cfg

    # -- Store validated config --
    hass.data[DOMAIN] = {"config": cfg}

    # -- Forward to sensor platform --
    try:
        from homeassistant.helpers.discovery import async_load_platform
        hass.async_create_task(
            async_load_platform(hass, "sensor", DOMAIN, {}, config)
        )
    except (ImportError, AttributeError):
        _LOGGER.debug("Platform forwarding skipped (standalone mode)")

    return True
