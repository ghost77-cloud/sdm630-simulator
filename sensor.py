import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
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
from . import CONF_ENTITIES
from .surplus_engine import (
    SurplusEngine,
    SensorSnapshot,
    CACHE_KEY_SOC,
    CACHE_KEY_POWER_TO_GRID,
    CACHE_KEY_PV_PRODUCTION,
    CACHE_KEY_POWER_TO_USER,
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
    sensor = SDM630SimSensor(name, hass, config)
    async_add_entities([sensor])


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
        self._sensor_cache: dict = {}
        self._engine: SurplusEngine | None = None
        self._first_tick: bool = True
        self._entity_to_cache_key: dict[str, str] = {}

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
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        entity_id = new_state.entity_id
        cache_key = self._entity_to_cache_key.get(entity_id)
        if cache_key is None:
            return
        try:
            self._sensor_cache[cache_key] = float(new_state.state)
        except (ValueError, TypeError) as exc:
            _LOGGER.debug("Cannot parse state for %s: %s", entity_id, exc)

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
            soc_percent     = self._sensor_cache.get(CACHE_KEY_SOC, 0.0),
            power_to_grid_w = self._sensor_cache.get(CACHE_KEY_POWER_TO_GRID, 0.0),
            pv_production_w = self._sensor_cache.get(CACHE_KEY_PV_PRODUCTION, 0.0),
            power_to_user_w = self._sensor_cache.get(CACHE_KEY_POWER_TO_USER, 0.0),
            timestamp       = now,
            sunset_time     = sunset_time,
            sunrise_time    = sunrise_time,
        )

        result = await self._engine.evaluate_cycle(snapshot)
        input_data_block.set_float(TOTAL_POWER, result.reported_kw)
        self._attr_native_value = result.reported_kw
        self.async_write_ha_state()

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
