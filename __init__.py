"""
Home Assistant custom component to simulate an Eastron SDM630 smart meter.
"""
import os
import sys

DOMAIN = "sdm630_simulator"

# Add the current directory to Python path when running standalone
if __package__ is None:
    DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, DIR)

async def async_setup(hass, config):
    """Set up the SDM630 simulator component."""
    # Placeholder for setup logic
    return True
