import logging
from datetime import timedelta
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util
from pymodbus.server import StartAsyncSerialServer
from pymodbus.framer import FramerType
from .modbus_server import (
    context,
    identity,
    input_data_block,
)
from .sdm630_input_registers import TOTAL_POWER
from . import CONF_ENTITIES, DEFAULTS
from .surplus_engine import (
    SurplusEngine,
    SensorSnapshot,
    EvaluationResult,
    CACHE_KEY_SOC,
    CACHE_KEY_POWER_TO_GRID,
    CACHE_KEY_PV_PRODUCTION,
    CACHE_KEY_POWER_TO_USER,
    SOC_HARD_FLOOR,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SDM630 Simulated Meter"
SCAN_INTERVAL = timedelta(seconds=10)

# Maps entity role keys (from config['entities']) to sensor cache keys.
# Only numeric state subscriptions are listed here (sun/weather are excluded).
ENTITY_ROLE_TO_CACHE_KEY = {
    "soc":           CACHE_KEY_SOC,
    "power_to_grid": CACHE_KEY_POWER_TO_GRID,
    "pv_production": CACHE_KEY_PV_PRODUCTION,
    "power_to_user": CACHE_KEY_POWER_TO_USER,
}


async def start_modbus_server():
    """Start the Modbus server asynchronously."""
    try:
        _LOGGER.info("Starting SDM630 Modbus Serial Simulator...")
        await StartAsyncSerialServer(
            context=context,
            identity=identity,
            port="/dev/ttyACM2",
            framer=FramerType.RTU,
            stopbits=1,
            bytesize=8,
            parity="E",
            baudrate="9600",
            handle_local_echo=True,
        )
    except Exception as e:
        _LOGGER.error("Failed to start Modbus server: %s", str(e))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SDM630 simulated sensor."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    hass.loop.create_task(start_modbus_server())

    raw_surplus_sensor = SDM630RawSurplusSensor()
    reported_surplus_sensor = SDM630ReportedSurplusSensor()
    sensor = SDM630SimSensor(name, hass, config)
    sensor.set_surplus_sensors(raw_surplus_sensor, reported_surplus_sensor)

    async_add_entities([sensor, raw_surplus_sensor, reported_surplus_sensor])


class SDM630RawSurplusSensor(RestoreSensor):
    """Sensor exposing raw (unfiltered) surplus power in W."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self) -> None:
        self._attr_name = "SDM Raw Surplus"
        self._attr_unique_id = "sdm_raw_surplus"
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data and last_data.native_value is not None:
            try:
                self._attr_native_value = float(last_data.native_value)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not restore raw surplus value: %r",
                                last_data.native_value)

    @callback
    def update_value(self, value_w: float) -> None:
        """Push a new surplus value (in W) — non-blocking, called from evaluation tick."""
        self._attr_native_value = round(value_w, 1)
        self.async_write_ha_state()


class SDM630ReportedSurplusSensor(RestoreSensor):
    """Sensor exposing reported (hysteresis-filtered) surplus power in W."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self) -> None:
        self._attr_name = "SDM Reported Surplus"
        self._attr_unique_id = "sdm_reported_surplus"
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data and last_data.native_value is not None:
            try:
                self._attr_native_value = float(last_data.native_value)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not restore reported surplus value: %r",
                                last_data.native_value)

    @callback
    def update_value(self, value_w: float) -> None:
        """Push a new surplus value (in W) — non-blocking, called from evaluation tick."""
        self._attr_native_value = round(value_w, 1)
        self.async_write_ha_state()


class SDM630SimSensor(SensorEntity):
    def __init__(self, name, hass, config):
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = "Watt"
        self._attr_unique_id = "sdm630_simulator_power"
        self._attr_should_poll = False
        self.hass = hass
        self._config = config
        self._sensor_cache: dict[str, tuple[float, object, bool]] = {}
        self._engine: SurplusEngine | None = None
        self._first_tick: bool = True
        self._entity_to_cache_key: dict[str, str] = {}
        self._cache_key_to_entity: dict[str, str] = {}
        self._failsafe_reason_logged: str | None = None
        self._invalidation_reasons: dict[str, str] = {}
        self._raw_surplus_sensor: SDM630RawSurplusSensor | None = None
        self._reported_surplus_sensor: SDM630ReportedSurplusSensor | None = None

    def set_surplus_sensors(
        self,
        raw_sensor: "SDM630RawSurplusSensor",
        reported_sensor: "SDM630ReportedSurplusSensor",
    ) -> None:
        """Store references to the surplus dashboard sensors."""
        self._raw_surplus_sensor = raw_sensor
        self._reported_surplus_sensor = reported_sensor

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        self._engine = SurplusEngine(self._config)

        entities_cfg = self._config.get(CONF_ENTITIES, {})
        self._entity_to_cache_key: dict[str, str] = {
            entity_id: ENTITY_ROLE_TO_CACHE_KEY[role]
            for role, entity_id in entities_cfg.items()
            if role in ENTITY_ROLE_TO_CACHE_KEY
        }
        self._cache_key_to_entity: dict[str, str] = {
            v: k for k, v in self._entity_to_cache_key.items()
        }
        numeric_entity_ids = list(self._entity_to_cache_key.keys())

        if numeric_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, numeric_entity_ids, self._handle_state_change
                )
            )

        interval = timedelta(seconds=self._config.get("evaluation_interval", 15))
        self.async_on_remove(
            async_track_time_interval(self.hass, self._evaluation_tick, interval)
        )

    @callback
    def _handle_state_change(self, event) -> None:
        """Update sensor cache on state change — no Modbus write here."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        entity_id = new_state.entity_id
        cache_key = self._entity_to_cache_key.get(entity_id)
        if cache_key is None:
            return
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            last_val = self._sensor_cache.get(cache_key, (0.0, None, True))[0]
            self._sensor_cache[cache_key] = (last_val, dt_util.utcnow(), False)
            self._invalidation_reasons[cache_key] = f" = {new_state.state}"
            return
        try:
            self._sensor_cache[cache_key] = (
                float(new_state.state), new_state.last_changed, True
            )
            self._invalidation_reasons.pop(cache_key, None)
        except (ValueError, TypeError):
            last_val = self._sensor_cache.get(cache_key, (0.0, None, True))[0]
            self._sensor_cache[cache_key] = (last_val, dt_util.utcnow(), False)
            self._invalidation_reasons[cache_key] = ": non-numeric value"
            _LOGGER.debug(
                "Cache invalidated for %s: non-numeric value '%s'",
                entity_id, new_state.state,
            )

    def _check_staleness(self) -> str:
        """Check critical sensor cache entries for staleness (Story 4.2).

        Returns a non-empty reason string and triggers FAILSAFE if any critical
        sensor's last_changed timestamp exceeds stale_threshold_seconds.
        Returns empty string if all critical sensors are fresh.
        Sensors absent from _cache_key_to_entity or with None timestamps are
        silently skipped (startup grace — AC4, AC5).
        """
        threshold: int = self._config.get("stale_threshold_seconds", 60)
        now = dt_util.utcnow()
        critical_keys = (CACHE_KEY_SOC, CACHE_KEY_PV_PRODUCTION, CACHE_KEY_POWER_TO_USER)

        for cache_key in critical_keys:
            entity_id = self._cache_key_to_entity.get(cache_key)
            if entity_id is None:
                continue  # not configured — AC5

            entry = self._sensor_cache.get(cache_key)
            if entry is None:
                continue  # not in cache yet — startup grace

            _value, last_changed, _is_valid = entry
            if last_changed is None:
                continue  # explicit startup grace sentinel — AC4

            elapsed = (now - last_changed).total_seconds()
            if elapsed > threshold:  # strict > — AC3
                reason = f"{entity_id} stale for {int(elapsed)}s"
                _LOGGER.warning(
                    "SDM630 FAIL-SAFE: %s stale for %ds. Reporting 0 kW.",
                    entity_id,
                    int(elapsed),
                )
                self._engine.hysteresis_filter.force_failsafe(reason)
                return reason

        return ""

    async def _evaluation_tick(self, now) -> None:
        """Called by async_track_time_interval at each evaluation cycle."""
        if self._first_tick:
            entities = self._config.get(CONF_ENTITIES, {})
            _LOGGER.info(
                "SDM630 SurplusEngine started. Interval=%ds, entities=%d configured",
                self._config.get("evaluation_interval", 15),
                len(entities),
            )
            self._first_tick = False

        # Story 4.2: staleness detection (force_failsafe called internally if stale)
        stale_reason = self._check_staleness()

        # Story 4.1: sensor-unavailability fail-safe guard (skip if already stale)
        if stale_reason:
            failsafe_reason = stale_reason
        else:
            cache_valid, validity_reason = self._check_cache_validity()
            if not cache_valid:
                self._engine.hysteresis_filter.force_failsafe(validity_reason)
                failsafe_reason = validity_reason
            else:
                failsafe_reason = ""

        if failsafe_reason:
            if self._failsafe_reason_logged != failsafe_reason:
                _LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", failsafe_reason)
                self._failsafe_reason_logged = failsafe_reason
            else:
                _LOGGER.debug("SDM630 FAIL-SAFE (ongoing): %s", failsafe_reason)
            result = EvaluationResult(
                reported_kw=0.0,
                real_surplus_kw=0.0,
                buffer_used_kw=0.0,
                soc_percent=self._sensor_cache.get(CACHE_KEY_SOC, (0.0,))[0],
                soc_floor_active=SOC_HARD_FLOOR,
                charging_state="FAILSAFE",
                reason=failsafe_reason,
                forecast_available=False,
            )
            _LOGGER.debug(
                "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
                "state=%s reported=%.2fkW reason=%s forecast=%s",
                result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
                result.soc_floor_active, result.charging_state, result.reported_kw,
                result.reason, result.forecast_available,
            )
            self._write_result(result)
            return

        # Story 4.4: value range validation (runs only when unavailability/staleness checks pass)
        range_fail = self._validate_cache()
        if range_fail:
            self._engine.hysteresis_filter.force_failsafe(range_fail)
            if self._failsafe_reason_logged != range_fail:
                _LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", range_fail)
                self._failsafe_reason_logged = range_fail
            else:
                _LOGGER.debug("SDM630 FAIL-SAFE (ongoing): %s", range_fail)
            result = EvaluationResult(
                reported_kw=0.0,
                real_surplus_kw=0.0,
                buffer_used_kw=0.0,
                soc_percent=self._sensor_cache.get(CACHE_KEY_SOC, (0.0,))[0],
                soc_floor_active=SOC_HARD_FLOOR,
                charging_state="FAILSAFE",
                reason=range_fail,
                forecast_available=False,
            )
            self._write_result(result)
            return

        # Recovery: staleness, validity, and range checks all passed
        if self._failsafe_reason_logged is not None:
            self._engine.hysteresis_filter.resume()
            _LOGGER.info("SDM630 recovered from FAILSAFE. Resuming normal evaluation.")
            self._failsafe_reason_logged = None

        sunset_time = None
        sunrise_time = None
        sun_state = self.hass.states.get("sun.sun")
        if sun_state and sun_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            raw_setting = sun_state.attributes.get("next_setting")
            raw_rising  = sun_state.attributes.get("next_rising")
            if raw_setting:
                sunset_time  = dt_util.parse_datetime(raw_setting)
            if raw_rising:
                sunrise_time = dt_util.parse_datetime(raw_rising)
        else:
            _LOGGER.debug("sun.sun unavailable — solar boundary times set to None")

        snapshot = SensorSnapshot(
            soc_percent     = self._sensor_cache.get(CACHE_KEY_SOC, (0.0, None, False))[0],
            power_to_grid_w = self._sensor_cache.get(CACHE_KEY_POWER_TO_GRID, (0.0, None, False))[0],
            pv_production_w = self._sensor_cache.get(CACHE_KEY_PV_PRODUCTION, (0.0, None, False))[0],
            power_to_user_w = self._sensor_cache.get(CACHE_KEY_POWER_TO_USER, (0.0, None, False))[0],
            timestamp       = now,
            sunset_time     = sunset_time,
            sunrise_time    = sunrise_time,
        )

        result = await self._engine.evaluate_cycle(snapshot, hass=self.hass)

        # Story 1.4: structured decision log
        _LOGGER.debug(
            "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
            "state=%s reported=%.2fkW reason=%s forecast=%s",
            result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
            result.soc_floor_active, result.charging_state, result.reported_kw,
            result.reason, result.forecast_available,
        )
        if result.charging_state == "FAILSAFE":
            _LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", result.reason)

        self._write_result(result)

    def _validate_cache(self) -> "str | None":
        """Validate cache values are within plausible ranges (Story 4.4).

        Returns a reason string if any valid cache entry is out of range,
        or None if all checks pass. Skips entries already marked invalid
        (valid=False) — Story 4.1 handles those independently (AC7).
        """
        ranges = self._config.get("sensor_ranges", DEFAULTS["sensor_ranges"])
        checks = [
            (CACHE_KEY_SOC,           "soc"),
            (CACHE_KEY_POWER_TO_GRID, "power_w"),
            (CACHE_KEY_PV_PRODUCTION, "power_w"),
            (CACHE_KEY_POWER_TO_USER, "power_w"),
        ]
        for cache_key, range_key in checks:
            entry = self._sensor_cache.get(cache_key)
            if entry is None or not entry[2]:  # missing or valid=False: defer to Story 4.1
                continue
            rng = ranges.get(range_key)
            if rng is None:
                continue
            min_val, max_val = rng
            value = entry[0]
            if not (min_val <= value <= max_val):
                entity_id = self._cache_key_to_entity.get(cache_key, cache_key)
                return (
                    f"{entity_id}: value {value} out of range [{min_val}, {max_val}]"
                )
        return None

    def _check_cache_validity(self) -> tuple[bool, str]:
        """Return (is_valid, reason). FAILSAFE reason set if any required entry is missing or invalid."""
        required_keys = [
            CACHE_KEY_SOC,
            CACHE_KEY_POWER_TO_GRID,
            CACHE_KEY_PV_PRODUCTION,
            CACHE_KEY_POWER_TO_USER,
        ]
        for cache_key in required_keys:
            entry = self._sensor_cache.get(cache_key)
            entity_id = self._cache_key_to_entity.get(cache_key, cache_key)
            if entry is None:
                return False, f"{entity_id}: no data received"
            if not entry[2]:
                reason_detail = self._invalidation_reasons.get(cache_key, " = unavailable")
                return False, f"{entity_id}{reason_detail}"
        return True, ""

    def _write_result(self, result: EvaluationResult) -> None:
        """Write evaluation result to Modbus register and HA state."""
        input_data_block.set_float(TOTAL_POWER, result.reported_kw)
        self._attr_native_value = result.reported_kw
        self.async_write_ha_state()
        self._update_surplus_sensors(result)

    def _update_surplus_sensors(self, result: EvaluationResult) -> None:
        """Push surplus values to dashboard sensors — non-blocking, fail-silent."""
        try:
            if self._raw_surplus_sensor is not None:
                self._raw_surplus_sensor.update_value(result.real_surplus_kw * 1000)
            if self._reported_surplus_sensor is not None:
                self._reported_surplus_sensor.update_value(result.reported_kw * 1000)
        except Exception:
            _LOGGER.warning("Failed to update surplus sensors", exc_info=True)
            return
        _LOGGER.debug(
            "SDM630 surplus sensors updated: raw=%.1fW reported=%.1fW",
            result.real_surplus_kw * 1000,
            result.reported_kw * 1000,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self._attr_unique_id
