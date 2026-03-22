"""Shared pytest fixtures and HA stubs for sdm630_simulator tests."""
import copy
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


# ---------------------------------------------------------------------------
# Story 5.1 — HA-free fixtures for SurplusCalculator tests
# ---------------------------------------------------------------------------

_SE_PATH = os.path.join(ROOT, "surplus_engine.py")
_SE_FIXTURE_KEY = "_surplus_engine_fixture"


def _load_se_fixture_mod():
    """Load surplus_engine standalone (no HA runtime) under a private module name."""
    if _SE_FIXTURE_KEY in sys.modules:
        return sys.modules[_SE_FIXTURE_KEY]
    spec = importlib.util.spec_from_file_location(_SE_FIXTURE_KEY, _SE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_SE_FIXTURE_KEY] = mod
    spec.loader.exec_module(mod)
    return mod


_se_fixture_mod = _load_se_fixture_mod()

# Sentinel: distinguishes "caller did not pass" from "caller passed None explicitly"
_UNSET = object()

TEST_CONFIG: dict = {
    "evaluation_interval": 15,
    "wallbox_threshold_kw": 4.2,
    "wallbox_min_kw": 4.1,
    "hold_time_minutes": 10,
    "soc_hard_floor": 50,
    "stale_threshold_seconds": 60,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
    "time_strategy": [
        {"before": "11:00", "soc_floor": 100},
        {"before": "sunset-3h", "soc_floor": 50},
        {"default": True, "soc_floor": 80},
    ],
}


@pytest.fixture
def base_config() -> dict:
    """Return a deep copy of TEST_CONFIG for each test."""
    return copy.deepcopy(TEST_CONFIG)


@pytest.fixture
def make_snapshot():
    """Factory fixture: call make_snapshot(**overrides) to get a SensorSnapshot.

    Pass sentinel _UNSET (default) for sunset_time / sunrise_time to get
    per-test defaults; pass None explicitly to test the 'no sunset' scenario.
    """
    from datetime import datetime, timezone  # local import to avoid top-level coupling
    _SensorSnapshot = _se_fixture_mod.SensorSnapshot

    def _factory(
        soc_percent: float = 80.0,
        power_to_grid_w: float = 0.0,
        pv_production_w: float = 5000.0,
        power_to_user_w: float = 1200.0,
        timestamp=None,
        sunset_time=_UNSET,
        sunrise_time=_UNSET,
        forecast=None,
    ):
        if timestamp is None:
            # Default: 12:30 on 2026-03-15 (March → seasonal=80, midday window)
            timestamp = datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc)
        if sunset_time is _UNSET:
            # Default: 18:00 same day → sunset-3h = 15:00
            sunset_time = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        if sunrise_time is _UNSET:
            # Default: 06:00 same day
            sunrise_time = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        return _SensorSnapshot(
            soc_percent=soc_percent,
            power_to_grid_w=power_to_grid_w,
            pv_production_w=pv_production_w,
            power_to_user_w=power_to_user_w,
            timestamp=timestamp,
            sunset_time=sunset_time,
            sunrise_time=sunrise_time,
            forecast=forecast,
        )

    return _factory


@pytest.fixture(scope="session")
def assert_no_ha_import(request):
    """Session finalizer: verifies surplus_engine loaded without HA imports.

    Checks that the standalone-loaded module (via spec_from_file_location)
    did not pull in any real homeassistant sub-modules.  The HA stubs
    installed by _install_ha_stubs() are types.ModuleType instances — they
    are excluded because they are not real packages.
    """
    def _check():
        real_ha = [
            k for k in sys.modules
            if (k == "homeassistant" or k.startswith("homeassistant."))
            and not isinstance(sys.modules[k], types.ModuleType)
        ]
        assert not real_ha, (
            f"Real homeassistant modules imported during tests!\n"
            f"Offending: {real_ha}"
        )

    request.addfinalizer(_check)
