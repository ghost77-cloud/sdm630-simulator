"""Shared pytest fixtures and HA stubs for sdm630_simulator tests."""
import importlib.util
import os
import sys
import types
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _install_ha_stubs() -> None:
    """Install lightweight homeassistant stubs so the component loads without HA."""
    if "homeassistant" in sys.modules:
        return  # already installed

    ha = types.ModuleType("homeassistant")
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_cv = types.ModuleType("homeassistant.helpers.config_validation")
    ha_discovery = types.ModuleType("homeassistant.helpers.discovery")

    def entity_id(value: str) -> str:
        if not isinstance(value, str) or "." not in value:
            raise vol.Invalid(f"Invalid entity_id: {value!r}")
        return value

    ha_cv.entity_id = entity_id
    ha_discovery.async_load_platform = AsyncMock(return_value=None)

    ha.helpers = ha_helpers
    ha_helpers.config_validation = ha_cv
    ha_helpers.discovery = ha_discovery

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.config_validation"] = ha_cv
    sys.modules["homeassistant.helpers.discovery"] = ha_discovery


# Install stubs before any test module is collected.
_install_ha_stubs()


@pytest.fixture(scope="session")
def comp():
    """Return the sdm630_simulator __init__ module (loaded once per session)."""
    # Remove any cached version so fresh load picks up stubs
    sys.modules.pop("sdm630_simulator", None)

    spec = importlib.util.spec_from_file_location(
        "sdm630_simulator", os.path.join(ROOT, "__init__.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sdm630_simulator"] = mod
    spec.loader.exec_module(mod)
    return mod
