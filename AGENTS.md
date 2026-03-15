# Project Guidelines

## Overview

Home Assistant custom component (`sdm630_simulator`) that simulates an Eastron SDM630 smart meter via Modbus TCP/RTU. Uses `pymodbus ≥3.9.2` for the Modbus server and exposes sensor entities in Home Assistant.

## Architecture

```txt
__init__.py          → HA component entry point (async_setup)
sensor.py            → HA sensor platform; starts Modbus serial server, tracks external entity state
modbus_server.py     → Modbus TCP server on :5020; SDM630DataBlock (ModbusSparseDataBlock)
registers.py         → Base classes: SDM630Register (dataclass), SDM630Registers (container)
sdm630_input_registers.py   → 51 read-only input registers (voltages, currents, power, energy)
sdm630_holding_registers.py → 11 writable holding registers (device configuration)
eastron/             → SDM630 protocol documentation (PDF)
chint/               → Chint meter documentation (PDF)
```

**Data flow**: External HA sensor state change → `SDM630SimSensor._handle_state_change()` → `input_data_block.set_float()` → register updated → Modbus clients see new values.

**Float encoding**: All register values are IEEE 754 floats stored as two consecutive 16-bit Modbus registers (`struct.pack('>f')`). Odd addresses = first register of a 32-bit pair.

## Code Style

- Python 3.9+, async/await for HA integration
- Classes: `CamelCase` (e.g., `SDM630Register`, `SDM630DataBlock`)
- Functions: `snake_case` (e.g., `float_to_regs`, `async_setup_platform`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `PHASE_1_VOLTAGE`, `TOTAL_POWER`)
- Logging via `logging.getLogger(__name__)` as `_LOGGER`
- All modules support dual import: as HA package and standalone (`if __package__:` guard)

## Conventions

- Register addresses use named constants, not raw integers
- Register objects use an observer pattern: `set_value_change_callback()` for reactive updates
- `negative_to_grid` flag on registers indicates negative values = power feeding to grid
- Sensor entities are event-driven (`_attr_should_poll = False`), not polled
- Holding register writes trigger callbacks with old/new values for logging

## Build and Test

- **Install**: Copy to `custom_components/sdm630_simulator/` in Home Assistant
- **Configure**: Add `sdm630_sim:` to `configuration.yaml`, restart HA
- **Dependencies**: `pip install pymodbus>=3.9.2`
- **Standalone test**: `python modbus_server.py` starts TCP server on port 5020
- **No test suite exists yet** — when adding tests, use `pytest` with `pytest-asyncio` for async code

## Key References

- SDM630 Modbus register map: [eastron/SDM630_MODBUS_Protocol.pdf](eastron/SDM630_MODBUS_Protocol.pdf)
- Chint meter docs: [chint/](chint/) (for future multi-meter support)
