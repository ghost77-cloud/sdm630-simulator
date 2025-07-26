import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, ENERGY_WATT_HOUR, POWER_WATT
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SDM630 Simulated Meter"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SDM630 simulated sensor."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    async_add_entities([SDM630SimSensor(name)])

class SDM630SimSensor(SensorEntity):
    def __init__(self, name):
        self._attr_name = name
        self._attr_native_value = 1234.5
        self._attr_native_unit_of_measurement = POWER_WATT
        self._attr_unique_id = "sdm630_simulator_power"

    @property
    def name(self):
        return self._attr_name

    @property
    def native_value(self):
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self):
        return self._attr_native_unit_of_measurement

    @property
    def unique_id(self):
        return self._attr_unique_id
