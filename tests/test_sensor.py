"""Tests for Story 1.3 — Integration Wiring in sensor.py and Evaluation Loop.

Covers all Acceptance Criteria:
  AC1 – SurplusEngine instantiation and state-change subscriptions
  AC2 – State-change handler: cache update only (no Modbus write)
  AC3 – Evaluation tick: SensorSnapshot assembly and engine call
  AC4 – SensorSnapshot: sun.sun solar boundary times
  AC5 – Startup INFO log
  AC6 – Lifecycle cleanup (async_on_remove called for all subscriptions)
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import sys
import types
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SENSOR_PATH = os.path.join(ROOT, "sensor.py")
_SE_PATH = os.path.join(ROOT, "surplus_engine.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_surplus_engine():
    """Load surplus_engine as a standalone module (no HA runtime)."""
    key = "_test_surplus_engine"
    sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(key, _SE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Main fixture — loads sensor.py with all stubs installed
# ---------------------------------------------------------------------------

@pytest.fixture
def sensor_ctx():
    """Install HA + component stubs, load sensor.py, yield (mod, mocks)."""
    se = _load_surplus_engine()

    # ── HA stubs ──────────────────────────────────────────────────────────
    ha_comps    = types.ModuleType("homeassistant.components")
    ha_sensor_m = types.ModuleType("homeassistant.components.sensor")

    class _SensorEntity:
        _attr_name = None
        _attr_native_value = None
        _attr_native_unit_of_measurement = None
        _attr_unique_id = None
        _attr_should_poll = True
        hass = None

        async def async_added_to_hass(self):
            pass

        def async_on_remove(self, func):
            pass

        def async_write_ha_state(self):
            pass

    ha_sensor_m.SensorEntity = _SensorEntity

    ha_const = types.ModuleType("homeassistant.const")
    ha_const.CONF_NAME          = "name"
    ha_const.STATE_UNAVAILABLE  = "unavailable"
    ha_const.STATE_UNKNOWN      = "unknown"

    ha_core          = types.ModuleType("homeassistant.core")
    ha_core.callback = lambda f: f          # pass-through decorator

    mock_track_state = MagicMock(return_value=MagicMock(name="unsub_state"))
    mock_track_time  = MagicMock(return_value=MagicMock(name="unsub_time"))

    ha_event = types.ModuleType("homeassistant.helpers.event")
    ha_event.async_track_state_change_event = mock_track_state
    ha_event.async_track_time_interval      = mock_track_time

    mock_parse_dt = MagicMock(
        return_value=datetime(2026, 6, 15, 20, 0, 0, tzinfo=timezone.utc)
    )
    ha_util    = types.ModuleType("homeassistant.util")
    ha_util_dt = types.ModuleType("homeassistant.util.dt")
    ha_util_dt.parse_datetime = mock_parse_dt
    ha_util.dt = ha_util_dt

    # ── pymodbus stubs ────────────────────────────────────────────────────
    pymodbus            = types.ModuleType("pymodbus")
    pymodbus_server     = types.ModuleType("pymodbus.server")
    pymodbus_server.StartAsyncSerialServer = AsyncMock()
    pymodbus_framer     = types.ModuleType("pymodbus.framer")
    pymodbus_framer.FramerType = MagicMock()

    # ── component stubs ───────────────────────────────────────────────────
    PKG = "sdm630_simulator"
    TOTAL_POWER = 0x0035

    mock_idb = MagicMock()
    mock_idb.set_float = MagicMock()

    pkg_modbus          = types.ModuleType(f"{PKG}.modbus_server")
    pkg_modbus.context  = MagicMock()
    pkg_modbus.identity = MagicMock()
    pkg_modbus.input_data_block = mock_idb

    pkg_regs            = types.ModuleType(f"{PKG}.sdm630_input_registers")
    pkg_regs.TOTAL_POWER = TOTAL_POWER

    # surplus_engine: re-export all public names from the real module
    pkg_se = types.ModuleType(f"{PKG}.surplus_engine")
    for attr in dir(se):
        if not attr.startswith("__"):
            setattr(pkg_se, attr, getattr(se, attr))

    # ── sys.modules installation ──────────────────────────────────────────
    new_modules: dict = {
        "homeassistant.components":             ha_comps,
        "homeassistant.components.sensor":      ha_sensor_m,
        "homeassistant.const":                  ha_const,
        "homeassistant.core":                   ha_core,
        "homeassistant.helpers.event":          ha_event,
        "homeassistant.util":                   ha_util,
        "homeassistant.util.dt":                ha_util_dt,
        "pymodbus":                             pymodbus,
        "pymodbus.server":                      pymodbus_server,
        "pymodbus.framer":                      pymodbus_framer,
        f"{PKG}.modbus_server":                 pkg_modbus,
        f"{PKG}.sdm630_input_registers":        pkg_regs,
        f"{PKG}.surplus_engine":                pkg_se,
    }

    saved = {k: sys.modules.get(k) for k in new_modules}
    for k, v in new_modules.items():
        sys.modules[k] = v

    # Ensure sdm630_simulator package exposes CONF_ENTITIES
    if PKG not in sys.modules:
        pkg_root = types.ModuleType(PKG)
        pkg_root.CONF_ENTITIES = "entities"
        sys.modules[PKG] = pkg_root
        saved[PKG] = None
    elif not hasattr(sys.modules[PKG], "CONF_ENTITIES"):
        sys.modules[PKG].CONF_ENTITIES = "entities"

    # Load sensor.py fresh
    sys.modules.pop(f"{PKG}.sensor", None)
    spec = importlib.util.spec_from_file_location(
        f"{PKG}.sensor", _SENSOR_PATH,
        submodule_search_locations=[ROOT],
    )
    sensor_mod = importlib.util.module_from_spec(spec)
    sensor_mod.__package__ = PKG
    sys.modules[f"{PKG}.sensor"] = sensor_mod
    spec.loader.exec_module(sensor_mod)

    mocks = {
        "track_state":    mock_track_state,
        "track_time":     mock_track_time,
        "input_data_block": mock_idb,
        "parse_datetime": mock_parse_dt,
        "TOTAL_POWER":    TOTAL_POWER,
        "se":             se,
        "SensorEntityBase": _SensorEntity,
        "STATE_UNAVAILABLE": "unavailable",
        "STATE_UNKNOWN":     "unknown",
    }

    yield sensor_mod, mocks

    # Cleanup
    sys.modules.pop(f"{PKG}.sensor", None)
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


@pytest.fixture
def sample_config():
    return {
        "name": "SDM630 Test",
        "evaluation_interval": 15,
        "entities": {
            "soc":           "sensor.battery_soc",
            "power_to_grid": "sensor.power_to_grid",
            "pv_production": "sensor.pv_power",
            "power_to_user": "sensor.power_to_user",
        },
    }


def _make_sensor(mod, hass, cfg):
    """Instantiate SDM630SimSensor with async_on_remove wired as a mock."""
    s = mod.SDM630SimSensor("Test Sensor", hass, cfg)
    s.async_on_remove = MagicMock()
    s.async_write_ha_state = MagicMock()
    # Build reverse entity→cache_key map (normally done in async_added_to_hass)
    entities_cfg = cfg.get("entities", {})
    s._entity_to_cache_key = {
        eid: mod.ENTITY_ROLE_TO_CACHE_KEY[role]
        for role, eid in entities_cfg.items()
        if role in mod.ENTITY_ROLE_TO_CACHE_KEY
    }
    return s


# ===========================================================================
# AC1 — Constructor: stores config, initializes cache/engine/first_tick
# ===========================================================================

class TestSensorInit:
    def test_stores_config(self, sensor_ctx, sample_config):
        mod, _ = sensor_ctx
        mock_hass = MagicMock()
        s = mod.SDM630SimSensor("Test", mock_hass, sample_config)
        assert s._config is sample_config

    def test_sensor_cache_empty_dict(self, sensor_ctx, sample_config):
        mod, _ = sensor_ctx
        s = mod.SDM630SimSensor("Test", MagicMock(), sample_config)
        assert s._sensor_cache == {}

    def test_engine_initially_none(self, sensor_ctx, sample_config):
        mod, _ = sensor_ctx
        s = mod.SDM630SimSensor("Test", MagicMock(), sample_config)
        assert s._engine is None

    def test_first_tick_initially_true(self, sensor_ctx, sample_config):
        mod, _ = sensor_ctx
        s = mod.SDM630SimSensor("Test", MagicMock(), sample_config)
        assert s._first_tick is True

    def test_should_poll_disabled(self, sensor_ctx, sample_config):
        mod, _ = sensor_ctx
        s = mod.SDM630SimSensor("Test", MagicMock(), sample_config)
        assert s._attr_should_poll is False


# ===========================================================================
# AC1 — async_added_to_hass: SurplusEngine created, subscriptions registered
# ===========================================================================

class TestAsyncAddedToHass:
    def test_engine_created(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        assert isinstance(s._engine, se.SurplusEngine)

    def test_state_change_subscription_registered(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        mocks["track_state"].reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        mocks["track_state"].assert_called_once()

    def test_numeric_entity_ids_passed_to_subscription(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        mocks["track_state"].reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        entity_ids = mocks["track_state"].call_args[0][1]
        assert "sensor.battery_soc" in entity_ids
        assert "sensor.power_to_grid" in entity_ids
        assert "sensor.pv_power" in entity_ids
        assert "sensor.power_to_user" in entity_ids

    def test_sun_and_weather_excluded_from_state_subscription(self, sensor_ctx):
        mod, mocks = sensor_ctx
        cfg = {
            "evaluation_interval": 15,
            "entities": {
                "soc":            "sensor.battery_soc",
                "power_to_grid":  "sensor.power_to_grid",
                "pv_production":  "sensor.pv_power",
                "power_to_user":  "sensor.power_to_user",
                "weather":         "weather.local",
                "forecast_solar":  "sensor.forecast_solar",
            },
        }
        mocks["track_state"].reset_mock()
        s = _make_sensor(mod, MagicMock(), cfg)
        asyncio.run(s.async_added_to_hass())
        entity_ids = mocks["track_state"].call_args[0][1]
        assert "weather.local" not in entity_ids
        assert "sensor.forecast_solar" not in entity_ids

    def test_time_interval_subscription_registered(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        mocks["track_time"].reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        mocks["track_time"].assert_called_once()

    def test_interval_uses_config_value(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        mocks["track_time"].reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        interval_arg = mocks["track_time"].call_args[0][2]
        assert interval_arg == timedelta(seconds=15)

    def test_state_unsub_registered_with_async_on_remove(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        mocks["track_state"].reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        # async_on_remove must have been called with the state change unsub
        unsub_state = mocks["track_state"].return_value
        remove_calls = [c[0][0] for c in s.async_on_remove.call_args_list]
        assert unsub_state in remove_calls

    def test_time_unsub_registered_with_async_on_remove(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        mocks["track_time"].reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())
        unsub_time = mocks["track_time"].return_value
        remove_calls = [c[0][0] for c in s.async_on_remove.call_args_list]
        assert unsub_time in remove_calls


# ===========================================================================
# AC2 — _handle_state_change: cache update only, no Modbus write
# ===========================================================================

def _make_event(entity_id: str, state_str: str):
    """Create a minimal HA state-change event mock."""
    new_state = MagicMock()
    new_state.entity_id = entity_id
    new_state.state = state_str
    event = MagicMock()
    event.data = {"new_state": new_state}
    return event


class TestHandleStateChange:
    def test_valid_state_updates_cache(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = _make_event("sensor.battery_soc", "75.5")
        s._handle_state_change(event)
        assert s._sensor_cache.get("soc_percent") == pytest.approx(75.5)

    def test_power_to_grid_maps_correct_key(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = _make_event("sensor.power_to_grid", "1200.0")
        s._handle_state_change(event)
        assert s._sensor_cache.get("power_to_grid_w") == pytest.approx(1200.0)

    def test_state_unavailable_does_not_update_cache(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        s._sensor_cache["soc_percent"] = 50.0   # pre-populate
        event = _make_event("sensor.battery_soc", "unavailable")
        s._handle_state_change(event)
        assert s._sensor_cache.get("soc_percent") == pytest.approx(50.0)  # unchanged

    def test_state_unknown_does_not_update_cache(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        s._sensor_cache["soc_percent"] = 60.0
        event = _make_event("sensor.battery_soc", "unknown")
        s._handle_state_change(event)
        assert s._sensor_cache.get("soc_percent") == pytest.approx(60.0)

    def test_none_new_state_is_ignored(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = MagicMock()
        event.data = {"new_state": None}
        s._handle_state_change(event)           # must not raise
        assert s._sensor_cache == {}

    def test_invalid_numeric_string_does_not_update_cache(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = _make_event("sensor.battery_soc", "not-a-number")
        s._handle_state_change(event)
        assert "soc_percent" not in s._sensor_cache

    def test_no_modbus_write_in_handle_state_change(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = _make_event("sensor.battery_soc", "80.0")
        s._handle_state_change(event)
        mocks["input_data_block"].set_float.assert_not_called()

    def test_pv_production_updates_cache(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = _make_event("sensor.pv_power", "3500.0")
        s._handle_state_change(event)
        assert s._sensor_cache.get("pv_production_w") == pytest.approx(3500.0)

    def test_power_to_user_updates_cache(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        s = _make_sensor(mod, MagicMock(), sample_config)
        event = _make_event("sensor.power_to_user", "900.0")
        s._handle_state_change(event)
        assert s._sensor_cache.get("power_to_user_w") == pytest.approx(900.0)


# ===========================================================================
# AC3 — _evaluation_tick: snapshot assembly, engine call, Modbus write
# ===========================================================================

class TestEvaluationTick:
    def _run_tick(self, sensor, now=None):
        if now is None:
            now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        return asyncio.run(sensor._evaluation_tick(now))

    def test_engine_evaluate_cycle_called(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())

        # Patch engine with async mock that records calls
        mock_engine = MagicMock()
        mock_engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
            soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
            reason="test", forecast_available=False,
        ))
        s._engine = mock_engine
        self._run_tick(s)
        mock_engine.evaluate_cycle.assert_called_once()

    def test_snapshot_uses_cache_values(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())

        s._sensor_cache["soc_percent"]     = 80.0
        s._sensor_cache["power_to_grid_w"] = 1500.0
        s._sensor_cache["pv_production_w"] = 4000.0
        s._sensor_cache["power_to_user_w"] = 2000.0

        captured = {}

        async def _capture(snap, hass=None):
            captured["snap"] = snap
            return se.EvaluationResult(
                reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
                soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
                reason="test", forecast_available=False,
            )

        s._engine = MagicMock()
        s._engine.evaluate_cycle = _capture
        self._run_tick(s)

        snap = captured["snap"]
        assert isinstance(snap, se.SensorSnapshot)
        assert snap.soc_percent     == pytest.approx(80.0)
        assert snap.power_to_grid_w == pytest.approx(1500.0)
        assert snap.pv_production_w == pytest.approx(4000.0)
        assert snap.power_to_user_w == pytest.approx(2000.0)

    def test_empty_cache_uses_zero_defaults(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())

        captured = {}

        async def _capture(snap, hass=None):
            captured["snap"] = snap
            return se.EvaluationResult(
                reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
                soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
                reason="test", forecast_available=False,
            )

        s._engine = MagicMock()
        s._engine.evaluate_cycle = _capture
        self._run_tick(s)
        snap = captured["snap"]
        assert snap.soc_percent     == pytest.approx(0.0)
        assert snap.power_to_grid_w == pytest.approx(0.0)

    def test_modbus_register_written(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mocks["input_data_block"].set_float.reset_mock()
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())

        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=2.5, real_surplus_kw=2.5, buffer_used_kw=0.0,
            soc_percent=75.0, soc_floor_active=50, charging_state="ACTIVE",
            reason="test", forecast_available=False,
        ))
        self._run_tick(s)
        mocks["input_data_block"].set_float.assert_called_once_with(
            mocks["TOTAL_POWER"], pytest.approx(2.5)
        )

    def test_native_value_updated(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())

        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=3.7, real_surplus_kw=3.7, buffer_used_kw=0.0,
            soc_percent=70.0, soc_floor_active=50, charging_state="ACTIVE",
            reason="test", forecast_available=False,
        ))
        self._run_tick(s)
        assert s._attr_native_value == pytest.approx(3.7)

    def test_async_write_ha_state_called(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        s = _make_sensor(mod, MagicMock(), sample_config)
        asyncio.run(s.async_added_to_hass())

        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
            soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
            reason="test", forecast_available=False,
        ))
        self._run_tick(s)
        s.async_write_ha_state.assert_called_once()


# ===========================================================================
# AC4 — sun.sun solar boundary times
# ===========================================================================

class TestSunSolarBoundaryTimes:
    _PARSED_DT = datetime(2026, 6, 15, 20, 0, 0, tzinfo=timezone.utc)

    def _make_sun_state(self, setting="2026-06-15T20:00:00+00:00",
                        rising="2026-06-16T04:30:00+00:00", avail=True):
        state = MagicMock()
        state.state = "above_horizon" if avail else "unavailable"
        state.attributes = {}
        if setting is not None:
            state.attributes["next_setting"] = setting
        if rising is not None:
            state.attributes["next_rising"] = rising
        return state

    def test_sunset_and_sunrise_passed_to_snapshot(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]

        mock_hass = MagicMock()
        mock_hass.states.get.return_value = self._make_sun_state()

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())

        captured = {}

        async def _capture(snap, hass=None):
            captured["snap"] = snap
            return se.EvaluationResult(
                reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
                soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
                reason="test", forecast_available=False,
            )

        s._engine = MagicMock()
        s._engine.evaluate_cycle = _capture
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        asyncio.run(s._evaluation_tick(now))

        snap = captured["snap"]
        # dt_util.parse_datetime was mocked to return _PARSED_DT
        assert snap.sunset_time  is not None
        assert snap.sunrise_time is not None

    def test_sun_unavailable_sets_none_times(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]

        mock_hass = MagicMock()
        sun_state = MagicMock()
        sun_state.state = "unavailable"
        mock_hass.states.get.return_value = sun_state

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())

        captured = {}

        async def _capture(snap, hass=None):
            captured["snap"] = snap
            return se.EvaluationResult(
                reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
                soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
                reason="test", forecast_available=False,
            )

        s._engine = MagicMock()
        s._engine.evaluate_cycle = _capture
        asyncio.run(s._evaluation_tick(
            datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ))
        assert captured["snap"].sunset_time  is None
        assert captured["snap"].sunrise_time is None

    def test_sun_state_none_sets_none_times(self, sensor_ctx, sample_config):
        """hass.states.get('sun.sun') returns None → no crash, times are None."""
        mod, mocks = sensor_ctx
        se = mocks["se"]

        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None   # sun.sun unavailable

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())

        captured = {}

        async def _capture(snap, hass=None):
            captured["snap"] = snap
            return se.EvaluationResult(
                reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
                soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
                reason="test", forecast_available=False,
            )

        s._engine = MagicMock()
        s._engine.evaluate_cycle = _capture
        asyncio.run(s._evaluation_tick(
            datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ))
        assert captured["snap"].sunset_time  is None
        assert captured["snap"].sunrise_time is None

    def test_missing_sun_attribute_sets_corresponding_none(self, sensor_ctx, sample_config):
        """next_setting present but next_rising absent → sunrise_time=None."""
        mod, mocks = sensor_ctx
        se = mocks["se"]

        mock_hass = MagicMock()
        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"next_setting": "2026-06-15T20:00:00+00:00"}
        mock_hass.states.get.return_value = sun_state

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())

        captured = {}

        async def _capture(snap, hass=None):
            captured["snap"] = snap
            return se.EvaluationResult(
                reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
                soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
                reason="test", forecast_available=False,
            )

        s._engine = MagicMock()
        s._engine.evaluate_cycle = _capture
        asyncio.run(s._evaluation_tick(
            datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ))
        assert captured["snap"].sunset_time  is not None   # was parsed
        assert captured["snap"].sunrise_time is None       # attribute absent


# ===========================================================================
# AC5 — Startup INFO log on first tick only
# ===========================================================================

class TestStartupLog:
    def test_info_log_emitted_on_first_tick(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
            soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
            reason="test", forecast_available=False,
        ))

        with patch.object(mod._LOGGER, "info") as mock_info:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            mock_info.assert_called_once()
            log_msg = mock_info.call_args[0][0]
            assert "SurplusEngine started" in log_msg

    def test_info_log_not_emitted_on_second_tick(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
            soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
            reason="test", forecast_available=False,
        ))

        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        asyncio.run(s._evaluation_tick(now))   # first tick — sets _first_tick=False

        with patch.object(mod._LOGGER, "info") as mock_info:
            asyncio.run(s._evaluation_tick(now))  # second tick
            mock_info.assert_not_called()

    def test_first_tick_flag_reset_after_first_tick(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=se.EvaluationResult(
            reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
            soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
            reason="test", forecast_available=False,
        ))

        assert s._first_tick is True
        asyncio.run(s._evaluation_tick(
            datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ))
        assert s._first_tick is False


# ===========================================================================
# AC1/AC6 — async_setup_platform passes config to sensor
# ===========================================================================

class TestSetupPlatform:
    def test_setup_platform_passes_config_to_sensor(self, sensor_ctx, sample_config):
        """async_setup_platform must instantiate SDM630SimSensor with config arg."""
        mod, mocks = sensor_ctx
        mock_hass = MagicMock()
        mock_hass.loop = MagicMock()
        mock_hass.loop.create_task = MagicMock()
        added_entities = []

        def _add(entities):
            added_entities.extend(entities)

        asyncio.run(mod.async_setup_platform(mock_hass, sample_config, _add))
        assert len(added_entities) == 1
        sensor = added_entities[0]
        assert isinstance(sensor, mod.SDM630SimSensor)
        assert sensor._config is sample_config


# ===========================================================================
# Story 1.4 — Structured Decision Logging
# ===========================================================================


def _make_result(se, **overrides):
    """Build an EvaluationResult with sensible defaults, applying overrides."""
    defaults = dict(
        reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,
        soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",
        reason="test", forecast_available=False,
    )
    defaults.update(overrides)
    return se.EvaluationResult(**defaults)


# ===========================================================================
# AC1 — Per-cycle DEBUG log (exact format)
# ===========================================================================

class TestDebugDecisionLog:
    """Story 1.4 AC1: _evaluation_tick emits a DEBUG log per cycle."""

    def test_debug_log_called_on_every_tick(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=_make_result(se))

        with patch.object(mod._LOGGER, "debug") as mock_debug:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            # At least one debug call should contain "SDM630 Eval:"
            eval_calls = [c for c in mock_debug.call_args_list
                          if c[0][0].startswith("SDM630 Eval:")]
            assert len(eval_calls) == 1

    def test_debug_log_exact_format_string(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=_make_result(
            se, real_surplus_kw=1.23, buffer_used_kw=0.45,
            soc_percent=80.0, soc_floor_active=50,
            charging_state="ACTIVE", reported_kw=1.23,
            reason="surplus_available", forecast_available=True,
        ))

        with patch.object(mod._LOGGER, "debug") as mock_debug:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            eval_calls = [c for c in mock_debug.call_args_list
                          if c[0][0].startswith("SDM630 Eval:")]
            assert len(eval_calls) == 1
            fmt = eval_calls[0][0][0]
            assert "surplus=%.2fkW" in fmt
            assert "buffer=%.2fkW" in fmt
            assert "SOC=%d%%" in fmt
            assert "floor=%d%%" in fmt
            assert "state=%s" in fmt
            assert "reported=%.2fkW" in fmt
            assert "reason=%s" in fmt
            assert "forecast=%s" in fmt

    def test_debug_log_positional_args_order(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = _make_result(
            se, real_surplus_kw=2.50, buffer_used_kw=0.30,
            soc_percent=75.0, soc_floor_active=40,
            charging_state="ACTIVE", reported_kw=2.20,
            reason="surplus_ok", forecast_available=False,
        )
        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=result)

        with patch.object(mod._LOGGER, "debug") as mock_debug:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            eval_calls = [c for c in mock_debug.call_args_list
                          if c[0][0].startswith("SDM630 Eval:")]
            args = eval_calls[0][0][1:]  # positional args after format string
            assert args == (2.50, 0.30, 75.0, 40, "ACTIVE", 2.20, "surplus_ok", False)

    def test_debug_log_emitted_on_second_tick_too(self, sensor_ctx, sample_config):
        """DEBUG log fires every tick, not just the first."""
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=_make_result(se))

        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        asyncio.run(s._evaluation_tick(now))  # first tick

        with patch.object(mod._LOGGER, "debug") as mock_debug:
            asyncio.run(s._evaluation_tick(now))  # second tick
            eval_calls = [c for c in mock_debug.call_args_list
                          if c[0][0].startswith("SDM630 Eval:")]
            assert len(eval_calls) == 1


# ===========================================================================
# AC2 — Fail-safe WARNING log
# ===========================================================================

class TestFailsafeWarningLog:
    """Story 1.4 AC2: FAILSAFE triggers WARNING in addition to DEBUG."""

    def test_warning_emitted_on_failsafe(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = _make_result(
            se, charging_state="FAILSAFE", reason="sensor_stale",
        )
        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=result)

        with patch.object(mod._LOGGER, "warning") as mock_warn:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            mock_warn.assert_called_once()

    def test_warning_exact_format(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = _make_result(
            se, charging_state="FAILSAFE", reason="sensor_stale",
        )
        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=result)

        with patch.object(mod._LOGGER, "warning") as mock_warn:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            fmt = mock_warn.call_args[0][0]
            assert fmt == "SDM630 FAIL-SAFE: %s. Reporting 0 kW."
            assert mock_warn.call_args[0][1] == "sensor_stale"

    def test_no_warning_for_non_failsafe(self, sensor_ctx, sample_config):
        """ACTIVE state must NOT trigger a WARNING."""
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = _make_result(se, charging_state="ACTIVE", reason="surplus_ok")
        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=result)

        with patch.object(mod._LOGGER, "warning") as mock_warn:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            mock_warn.assert_not_called()

    def test_no_warning_for_inactive(self, sensor_ctx, sample_config):
        """INACTIVE state must NOT trigger a WARNING."""
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = _make_result(se, charging_state="INACTIVE", reason="no_surplus")
        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=result)

        with patch.object(mod._LOGGER, "warning") as mock_warn:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            mock_warn.assert_not_called()

    def test_both_debug_and_warning_on_failsafe(self, sensor_ctx, sample_config):
        """FAILSAFE emits BOTH DEBUG (full context) and WARNING."""
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = _make_result(
            se, charging_state="FAILSAFE", reason="sensor_stale",
        )
        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=result)

        with patch.object(mod._LOGGER, "debug") as mock_debug, \
             patch.object(mod._LOGGER, "warning") as mock_warn:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            eval_calls = [c for c in mock_debug.call_args_list
                          if c[0][0].startswith("SDM630 Eval:")]
            assert len(eval_calls) == 1
            mock_warn.assert_called_once()


# ===========================================================================
# AC4 — Startup INFO log format validation (extends Story 1.3 AC5 tests)
# ===========================================================================

class TestStartupLogFormat:
    """Story 1.4 AC4: validate exact format of startup INFO log."""

    def test_startup_log_exact_format(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=_make_result(se))

        with patch.object(mod._LOGGER, "info") as mock_info:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            fmt = mock_info.call_args[0][0]
            assert fmt == "SDM630 SurplusEngine started. Interval=%ds, entities=%d configured"

    def test_startup_log_args(self, sensor_ctx, sample_config):
        mod, mocks = sensor_ctx
        se = mocks["se"]
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        s = _make_sensor(mod, mock_hass, sample_config)
        asyncio.run(s.async_added_to_hass())
        s._engine = MagicMock()
        s._engine.evaluate_cycle = AsyncMock(return_value=_make_result(se))

        with patch.object(mod._LOGGER, "info") as mock_info:
            asyncio.run(s._evaluation_tick(
                datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            ))
            args = mock_info.call_args[0][1:]
            assert args == (15, 4)  # 15s interval, 4 entities
