# Project Guidelines

## Overview

Home Assistant custom component (`sdm630_simulator`) that simulates an
Eastron SDM630 smart meter via Modbus RTU (serial). Uses
`pymodbus >=3.11.1` for the Modbus server and exposes sensor entities
in Home Assistant. In production, the wallbox connects via RS485 to a
USB-serial adapter (`/dev/ttyACM2`, 9600 8E1). A standalone TCP server
on port 5020 exists for development testing only.
Includes a surplus engine that calculates PV excess power with battery
buffer, hysteresis filtering, forecast integration, and fail-safe
mechanisms — optimised for EV charging with the Growatt THOR wallbox.

## Architecture

```txt
__init__.py              → HA entry point (async_setup, config)
sensor.py                → Sensor platform; RTU serial server,
                           eval loop, cache, surplus/poll/
                           warning entities
modbus_server.py         → Modbus datastore + TCP test server
                           (:5020); SDM630DataBlock
surplus_engine.py        → SurplusEngine, SurplusCalculator,
                           HysteresisFilter, ForecastConsumer
registers.py             → SDM630Register, SDM630Registers
sdm630_input_registers.py
                         → 51 input registers (V, A, W, kWh)
sdm630_holding_registers.py
                         → 11 holding registers (config)
docs/lovelace-wallbox-card.yaml
                         → Ready-to-paste Lovelace card
eastron/                 → SDM630 protocol docs (PDF)
chint/                   → Chint meter docs (PDF)
tests/                   → pytest suite (calculator, hysteresis,
                           config, SOC, staleness, range, sensor)
```

**Data flow**: External HA sensor state change →
`SDM630SimSensor._handle_state_change()` → sensor cache updated →
evaluation tick (every 15 s) → safety checks →
`SurplusEngine.evaluate_cycle()` →
`HysteresisFilter.update()` →
`input_data_block.set_float(TOTAL_POWER)` →
Wallbox reads value via Modbus RTU FC04.

**Float encoding**: All register values are IEEE 754 floats stored as
two consecutive 16-bit Modbus registers (`struct.pack('>f')`). Odd
addresses = first register of a 32-bit pair.

## Code Style

- Python 3.9+, async/await for HA integration
- Classes: `CamelCase` (e.g., `SDM630Register`, `SurplusCalculator`)
- Functions: `snake_case` (e.g., `float_to_regs`, `async_setup_platform`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `PHASE_1_VOLTAGE`, `SOC_HARD_FLOOR`)
- Logging via `logging.getLogger(__name__)` as `_LOGGER`
- All modules support dual import: as HA package and standalone
  (`if __package__:` guard)

## Conventions

- Register addresses use named constants, not raw integers
- Register objects use an observer pattern:
  `set_value_change_callback()` for reactive updates
- `negative_to_grid` flag on registers indicates negative values = power
  feeding to grid
- Sensor entities are event-driven (`_attr_should_poll = False`), not
  polled
- Holding register writes trigger callbacks with old/new values for
  logging
- Surplus engine uses pure dataclasses (`SensorSnapshot`,
  `EvaluationResult`, `ForecastData`) — no HA dependencies in
  calculation logic
- Hard SOC floor (50 %) is enforced unconditionally in fail-safe path

## Build and Test

- **Install**: Copy to `custom_components/sdm630_simulator/` in Home
  Assistant
- **Configure**: Add `sdm630_sim:` block to `configuration.yaml`,
  restart HA
- **Dependencies**: `pip install pymodbus>=3.11.1`
- **Dev dependencies**: `pip install -r requirements-dev.txt`
- **Standalone test**: `python modbus_server.py` starts TCP
  test server on port 5020 (RTU framing over TCP)
- **Run tests**: `pytest` (uses `pytest-asyncio` for async code)
- **Lint**: `npx markdownlint-cli2 "**/*.md"` for Markdown files

## Key References

- SDM630 Modbus register map:
  [eastron/SDM630_MODBUS_Protocol.pdf](eastron/SDM630_MODBUS_Protocol.pdf)
- Chint meter docs: [chint/](chint/) (for future multi-meter support)
- Lovelace dashboard card:
  [docs/lovelace-wallbox-card.yaml](docs/lovelace-wallbox-card.yaml)
