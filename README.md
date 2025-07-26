# SDM630 Simulator

This custom component simulates an Eastron SDM630 smart meter for Home Assistant.

## Features
- Simulates MODBUS responses as per SDM630 protocol
- Exposes sensors/entities in Home Assistant

## Setup
1. Copy this folder to your `custom_components` directory.
2. Add `sdm630_sim:` to your `configuration.yaml`.
3. Restart Home Assistant.

## TODO
- Implement MODBUS TCP/RTU simulation
- Map SDM630 registers to simulated values
- Expose sensors in Home Assistant
