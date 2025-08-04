import logging
import asyncio
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.discovery import async_load_platform
from pymodbus.server import StartAsyncTcpServer
from .modbus_server import (
    context,
    identity,
    input_reg_manager,
)
from .sdm630_input_registers import TOTAL_POWER

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SDM630 Simulated Meter"
SCAN_INTERVAL = timedelta(seconds=10)  # Update every 10 seconds

async def start_modbus_server():
    """Start the Modbus server asynchronously."""
    try:
        await StartAsyncTcpServer(
            context,
            identity=identity,
            address=("0.0.0.0", 5020),
            framer="rtu"
        )
    except Exception as e:
        _LOGGER.error("Failed to start Modbus server: %s", str(e))

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SDM630 simulated sensor."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    
    # Start the Modbus server in the background
    hass.loop.create_task(start_modbus_server())
    
    async_add_entities([SDM630SimSensor(name)])

class SDM630SimSensor(SensorEntity):
    def __init__(self, name):
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = "Watt"
        self._attr_unique_id = "sdm630_simulator_power"
        self._attr_should_poll = True  # Enable polling
        self._attr_extra_state_attributes = {
            'total_requests': 0,
            'read_requests': 0,
            'write_requests': 0,
            'errors': 0
        }
        
    async def async_update(self):
        """Fetch new state data for the sensor."""
        try:
            # Get the power value from register 12 (Total System Power)
            self._attr_native_value = input_reg_manager.get_float(TOTAL_POWER)
            
            # Get server statistics
            stats = context.server.counter._data if hasattr(context, 'server') else None
            if stats:
                self._attr_extra_state_attributes = {
                    'total_requests': stats.get('Transaction', 0),
                    'read_requests': stats.get('Read', 0),
                    'write_requests': stats.get('Write', 0),
                    'errors': stats.get('Error', 0)
                }
            
            _LOGGER.debug("Updated sensor value to: %s", self._attr_native_value)
        except Exception as e:
            _LOGGER.error("Error updating sensor value: %s", str(e))
            self._attr_native_value = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attr_extra_state_attributes

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
        
    def set_power(self, value):
        """Set the power value in the Modbus register."""
        try:
            input_reg_manager.set_float(12, float(value))
            _LOGGER.info("Set power value to: %s", value)
        except Exception as e:
            _LOGGER.error("Error setting power value: %s", str(e))
