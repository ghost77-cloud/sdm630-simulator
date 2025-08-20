import logging
import asyncio
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_state_change_event
)
from pymodbus.server import StartAsyncSerialServer
from pymodbus.framer import FramerType
from .modbus_server import (
    context,
    identity,
    input_data_block,
)
from .sdm630_input_registers import TOTAL_POWER

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SDM630 Simulated Meter"
SCAN_INTERVAL = timedelta(seconds=10)  # Update every 10 seconds

async def start_modbus_server():
    """Start the Modbus server asynchronously."""
    try:

        _LOGGER.info(f"Starting SDM630 Modbus Serial Simulator...")
        await StartAsyncSerialServer(
            context=context,  # Data storage
            identity=identity,  # server identify
            # timeout=1,  # waiting time for request to complete
            port="/dev/ttyACM2",  # serial port
            # custom_functions=[],  # allow custom handling
            framer=FramerType.RTU,  # The framer strategy to use
            stopbits=1,  # The number of stop bits to use
            bytesize=8,  # The bytesize of the serial messages
            parity="E",  # Which kind of parity to use
            baudrate="9600",  # The baud rate to use for the serial device
            handle_local_echo=True,  # Handle local echo of the USB-to-RS485 adaptor
            # ignore_missing_devices=True,  # ignore request to a missing device
            # broadcast_enable=False,  # treat device_id 0 as broadcast address,
        )

    except Exception as e:
        _LOGGER.error("Failed to start Modbus server: %s", str(e))

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SDM630 simulated sensor."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    
    # Start the Modbus server in the background
    hass.loop.create_task(start_modbus_server())
    
    sensor = SDM630SimSensor(name, hass)
    async_add_entities([sensor])

class SDM630SimSensor(SensorEntity):
    def __init__(self, name, hass):
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = "Watt"
        self._attr_unique_id = "sdm630_simulator_power"
        self._attr_should_poll = False  # Disable polling since we'll use state tracking
        self.hass = hass
        
    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Start listening to state changes
        @callback
        def _handle_state_change(event):
            """Handle state changes of the tracked entity."""
            new_state = event.data.get("new_state")
            if new_state is not None:
                try:
                    new_value = float(new_state.state)
                    # Update both the register manager and Modbus store
                    input_data_block.set_float(TOTAL_POWER, new_value)
                    self._attr_native_value = new_value
                    self.async_write_ha_state()
                    _LOGGER.debug("Updated sensor value to: %s from external sensor", new_value)
                except (ValueError, TypeError) as e:
                    _LOGGER.error("Error processing new state value: %s", e)

        # Subscribe to state changes using async_track_state_change_event
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                ["sensor.sph10000_ac_to_grid_total", "sensor.sph10000_output_power"],
                _handle_state_change
            )
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
