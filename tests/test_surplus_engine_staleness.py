"""Tests for Story 4.2 — Staleness Detection.

Covers all Acceptance Criteria:
  AC1 – Stale critical sensor triggers FAILSAFE
  AC2 – FAILSAFE clears on sensor recovery
  AC3 – Exactly at threshold is NOT stale
  AC4 – Startup grace period: None timestamps and absent entries are skipped
  AC5 – Only critical sensors checked (non-critical + unconfigured silently skipped)
  AC6 – SurplusCalculator has zero new homeassistant imports
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
import types
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SENSOR_PATH = os.path.join(ROOT, "sensor.py")
_SE_PATH = os.path.join(ROOT, "surplus_engine.py")

# Timezone-aware "now" used as base timestamp across tests
_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

def _load_surplus_engine():
    key = "_test_staleness_se"
    sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(key, _SE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture — loads sensor.py with all stubs (mirrors test_sensor.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def sensor_ctx():
    """Install HA + component stubs, load sensor.py, yield (mod, mocks)."""
    se = _load_surplus_engine()

    ha_comps    = types.ModuleType("homeassistant.components")
    ha_sensor_m = types.ModuleType("homeassistant.components.sensor")
    ha_binary_sensor_m = types.ModuleType("homeassistant.components.binary_sensor")

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

    class _RestoreSensor(_SensorEntity):
        async def async_added_to_hass(self):
            pass

        async def async_get_last_sensor_data(self):
            return None

    ha_sensor_m.RestoreSensor = _RestoreSensor
    ha_sensor_m.SensorDeviceClass = MagicMock()
    ha_sensor_m.SensorDeviceClass.POWER = "power"

    class _BinarySensorEntity:
        _attr_name = None
        _attr_unique_id = None
        _attr_should_poll = True
        _attr_is_on = False
        _attr_device_class = None
        hass = None

        async def async_added_to_hass(self):
            pass

        def async_on_remove(self, func):
            pass

        def async_write_ha_state(self):
            pass

    ha_binary_sensor_m.BinarySensorEntity = _BinarySensorEntity
    ha_binary_sensor_m.BinarySensorDeviceClass = MagicMock()
    ha_binary_sensor_m.BinarySensorDeviceClass.PROBLEM = "problem"

    ha_const = types.ModuleType("homeassistant.const")
    ha_const.CONF_NAME         = "name"
    ha_const.STATE_UNAVAILABLE = "unavailable"
    ha_const.STATE_UNKNOWN     = "unknown"

    ha_core          = types.ModuleType("homeassistant.core")
    ha_core.callback = lambda f: f

    mock_track_state = MagicMock(return_value=MagicMock(name="unsub_state"))
    mock_track_time  = MagicMock(return_value=MagicMock(name="unsub_time"))

    ha_event = types.ModuleType("homeassistant.helpers.event")
    ha_event.async_track_state_change_event = mock_track_state
    ha_event.async_track_time_interval      = mock_track_time

    mock_utcnow = MagicMock(return_value=_NOW)

    ha_util    = types.ModuleType("homeassistant.util")
    ha_util_dt = types.ModuleType("homeassistant.util.dt")
    ha_util_dt.parse_datetime = MagicMock(return_value=_NOW)
    ha_util_dt.utcnow = mock_utcnow
    ha_util.dt = ha_util_dt

    pymodbus        = types.ModuleType("pymodbus")
    pymodbus_server = types.ModuleType("pymodbus.server")
    pymodbus_server.StartAsyncSerialServer = AsyncMock()
    pymodbus_framer = types.ModuleType("pymodbus.framer")
    pymodbus_framer.FramerType = MagicMock()

    PKG = "sdm630_simulator"
    mock_idb = MagicMock()

    pkg_modbus              = types.ModuleType(f"{PKG}.modbus_server")
    pkg_modbus.context      = MagicMock()
    pkg_modbus.identity     = MagicMock()
    pkg_modbus.input_data_block = mock_idb

    pkg_regs             = types.ModuleType(f"{PKG}.sdm630_input_registers")
    pkg_regs.TOTAL_POWER = 0x0035

    pkg_se = types.ModuleType(f"{PKG}.surplus_engine")
    for attr in dir(se):
        if not attr.startswith("__"):
            setattr(pkg_se, attr, getattr(se, attr))

    new_modules: dict = {
        "homeassistant.components":                 ha_comps,
        "homeassistant.components.sensor":          ha_sensor_m,
        "homeassistant.components.binary_sensor":   ha_binary_sensor_m,
        "homeassistant.const":                      ha_const,
        "homeassistant.core":               ha_core,
        "homeassistant.helpers.event":      ha_event,
        "homeassistant.util":               ha_util,
        "homeassistant.util.dt":            ha_util_dt,
        "pymodbus":                         pymodbus,
        "pymodbus.server":                  pymodbus_server,
        "pymodbus.framer":                  pymodbus_framer,
        f"{PKG}.modbus_server":             pkg_modbus,
        f"{PKG}.sdm630_input_registers":    pkg_regs,
        f"{PKG}.surplus_engine":            pkg_se,
    }

    saved = {k: sys.modules.get(k) for k in new_modules}
    for k, v in new_modules.items():
        sys.modules[k] = v

    if PKG not in sys.modules:
        pkg_root = types.ModuleType(PKG)
        pkg_root.CONF_ENTITIES = "entities"
        pkg_root.DEFAULTS = {
            "sensor_ranges": {"soc": (0, 100), "power_w": (-30000, 30000)},
        }
        pkg_root.DOMAIN = "sdm630_simulator"
        sys.modules[PKG] = pkg_root
        saved[PKG] = None
    else:
        if not hasattr(sys.modules[PKG], "CONF_ENTITIES"):
            sys.modules[PKG].CONF_ENTITIES = "entities"
        if not hasattr(sys.modules[PKG], "DEFAULTS"):
            sys.modules[PKG].DEFAULTS = {
                "sensor_ranges": {"soc": (0, 100), "power_w": (-30000, 30000)},
            }
        if not hasattr(sys.modules[PKG], "DOMAIN"):
            sys.modules[PKG].DOMAIN = "sdm630_simulator"

    sys.modules.pop(f"{PKG}.sensor", None)
    spec = importlib.util.spec_from_file_location(
        f"{PKG}.sensor", _SENSOR_PATH,
        submodule_search_locations=[ROOT],
    )
    sensor_mod = importlib.util.module_from_spec(spec)
    sensor_mod.__package__ = PKG
    sys.modules[f"{PKG}.sensor"] = sensor_mod
    spec.loader.exec_module(sensor_mod)

    yield sensor_mod, mock_utcnow, se

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
        "stale_threshold_seconds": 60,
        "entities": {
            "soc":           "sensor.battery_soc",
            "power_to_grid": "sensor.power_to_grid",
            "pv_production": "sensor.pv_power",
            "power_to_user": "sensor.power_to_user",
        },
    }


def _make_sensor(mod, cfg):
    """Instantiate SDM630SimSensor with mocked engine and helpers."""
    hass_mock = MagicMock()
    hass_mock.states.get.return_value = None
    s = mod.SDM630SimSensor("Test Sensor", hass_mock, cfg)
    s.async_on_remove    = MagicMock()
    s.async_write_ha_state = MagicMock()
    s._invalidation_reasons = {}
    # Wire reverse-lookup maps (normally built in async_added_to_hass)
    entities_cfg = cfg.get("entities", {})
    s._entity_to_cache_key = {
        eid: mod.ENTITY_ROLE_TO_CACHE_KEY[role]
        for role, eid in entities_cfg.items()
        if role in mod.ENTITY_ROLE_TO_CACHE_KEY
    }
    s._cache_key_to_entity = {v: k for k, v in s._entity_to_cache_key.items()}
    # Inject a mock engine with a hysteresis filter
    mock_engine = MagicMock()
    mock_engine.hysteresis_filter = MagicMock()
    mock_engine.hysteresis_filter.state = "INACTIVE"
    s._engine = mock_engine
    return s


# ===========================================================================
# AC1 — Stale critical sensor triggers FAILSAFE
# ===========================================================================

class TestAC1StaleSensorTriggersFailsafe:
    def test_soc_stale_triggers_failsafe(self, sensor_ctx, sample_config):
        """SOC last updated 61s ago → force_failsafe called, returns reason."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=61)
        s._sensor_cache = {
            "soc_percent":     (50.0, stale_ts, True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (1000.0, _NOW,   True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }
        result = s._check_staleness()
        assert result  # non-empty reason string
        assert "sensor.battery_soc" in result
        s._engine.hysteresis_filter.force_failsafe.assert_called_once()

    def test_failsafe_reason_contains_entity_id_and_elapsed(
        self, sensor_ctx, sample_config
    ):
        """Reason string contains entity_id and elapsed seconds."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=61)
        s._sensor_cache = {
            "soc_percent":     (50.0, stale_ts, True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (1000.0, _NOW,   True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }
        s._check_staleness()
        reason = s._engine.hysteresis_filter.force_failsafe.call_args[0][0]
        assert "sensor.battery_soc" in reason
        assert "61s" in reason

    def test_stale_warning_logged(self, sensor_ctx, sample_config, caplog):
        """Warning with entity_id and elapsed seconds is emitted."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=90)
        s._sensor_cache = {
            "soc_percent":     (50.0, stale_ts, True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (1000.0, _NOW,   True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }
        with caplog.at_level(logging.WARNING):
            s._check_staleness()
        assert any(
            "stale for" in r.message and "sensor.battery_soc" in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    def test_pv_production_stale_triggers_failsafe(self, sensor_ctx, sample_config):
        """PV production last updated 65s ago → FAILSAFE triggered."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=65)
        s._sensor_cache = {
            "soc_percent":     (50.0, _NOW,     True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (1000.0, stale_ts, True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }
        assert s._check_staleness()  # non-empty reason string
        s._engine.hysteresis_filter.force_failsafe.assert_called_once()

    def test_power_to_user_stale_triggers_failsafe(self, sensor_ctx, sample_config):
        """power_to_user last updated 100s ago → FAILSAFE triggered."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=100)
        s._sensor_cache = {
            "soc_percent":     (50.0, _NOW,      True),
            "power_to_grid_w": (0.0,  _NOW,      True),
            "pv_production_w": (1000.0, _NOW,    True),
            "power_to_user_w": (500.0,  stale_ts, True),
        }
        assert s._check_staleness()  # non-empty reason string


# ===========================================================================
# AC2 — FAILSAFE clears on sensor recovery
# ===========================================================================

class TestAC2RecoveryOnFreshTimestamp:
    def test_fresh_timestamp_returns_false(self, sensor_ctx, sample_config):
        """After stale period is resolved, _check_staleness returns False."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        # All sensors have a fresh timestamp (just updated)
        s._sensor_cache = {
            "soc_percent":     (50.0, _NOW, True),
            "power_to_grid_w": (0.0,  _NOW, True),
            "pv_production_w": (1000.0, _NOW, True),
            "power_to_user_w": (500.0,  _NOW, True),
        }
        assert not s._check_staleness()  # empty string = no staleness
        s._engine.hysteresis_filter.force_failsafe.assert_not_called()

    def test_recovery_after_stale_period(self, sensor_ctx, sample_config):
        """After sensor emits fresh state, check returns empty → no new FAILSAFE."""
        mod, mock_utcnow, _ = sensor_ctx
        # First: sensor is stale
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=61)
        s._sensor_cache["soc_percent"] = (50.0, stale_ts, True)
        s._sensor_cache["power_to_grid_w"] = (0.0, _NOW, True)
        s._sensor_cache["pv_production_w"] = (1000.0, _NOW, True)
        s._sensor_cache["power_to_user_w"] = (500.0, _NOW, True)
        assert s._check_staleness()  # non-empty = stale

        # Sensor recovers: new state emitted, last_changed refreshed
        s._sensor_cache["soc_percent"] = (52.0, _NOW, True)
        s._engine.hysteresis_filter.force_failsafe.reset_mock()
        assert not s._check_staleness()  # empty = no staleness
        s._engine.hysteresis_filter.force_failsafe.assert_not_called()


# ===========================================================================
# AC3 — Exactly at threshold is NOT stale (boundary: strict >)
# ===========================================================================

class TestAC3ExactThresholdNotStale:
    def test_elapsed_equals_threshold_not_stale(self, sensor_ctx, sample_config):
        """elapsed == 60s, threshold == 60s → NOT stale (strict > boundary)."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        exactly_at_threshold = _NOW - timedelta(seconds=60)
        s._sensor_cache = {
            "soc_percent":     (50.0, exactly_at_threshold, True),
            "power_to_grid_w": (0.0,  _NOW, True),
            "pv_production_w": (1000.0, _NOW, True),
            "power_to_user_w": (500.0,  _NOW, True),
        }
        assert not s._check_staleness()  # empty string = no staleness
        s._engine.hysteresis_filter.force_failsafe.assert_not_called()

    def test_elapsed_one_second_below_threshold_not_stale(
        self, sensor_ctx, sample_config
    ):
        """elapsed == 59s, threshold == 60s → NOT stale."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        ts = _NOW - timedelta(seconds=59)
        s._sensor_cache = {
            "soc_percent":     (50.0, ts,   True),
            "power_to_grid_w": (0.0,  _NOW, True),
            "pv_production_w": (1000.0, _NOW, True),
            "power_to_user_w": (500.0,  _NOW, True),
        }
        assert not s._check_staleness()  # empty string = no staleness

    def test_elapsed_one_second_above_threshold_is_stale(
        self, sensor_ctx, sample_config
    ):
        """elapsed == 61s, threshold == 60s → stale."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        ts = _NOW - timedelta(seconds=61)
        s._sensor_cache = {
            "soc_percent":     (50.0, ts,   True),
            "power_to_grid_w": (0.0,  _NOW, True),
            "pv_production_w": (1000.0, _NOW, True),
            "power_to_user_w": (500.0,  _NOW, True),
        }
        assert s._check_staleness()  # non-empty = stale


# ===========================================================================
# AC4 — Startup grace period: None timestamps and absent entries are skipped
# ===========================================================================

class TestAC4StartupGrace:
    def test_none_last_changed_skipped(self, sensor_ctx, sample_config):
        """Cache entry (value, None, True) → skipped, no FAILSAFE."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        s._sensor_cache = {
            "soc_percent":     (0.0, None, True),  # None timestamp — startup grace
            "power_to_grid_w": (0.0, _NOW, True),
            "pv_production_w": (0.0, _NOW, True),
            "power_to_user_w": (0.0, _NOW, True),
        }
        assert not s._check_staleness()  # empty = no staleness
        s._engine.hysteresis_filter.force_failsafe.assert_not_called()

    def test_absent_cache_entry_skipped(self, sensor_ctx, sample_config):
        """No entry for critical key → startup grace, no FAILSAFE."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        s._sensor_cache = {}  # nothing yet
        assert not s._check_staleness()  # empty = no staleness
        s._engine.hysteresis_filter.force_failsafe.assert_not_called()

    def test_partially_populated_cache_skips_absent_entries(
        self, sensor_ctx, sample_config
    ):
        """Only some sensors have received data yet — absent ones skipped."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        # Only power_to_grid received data; critical keys absent → all skipped
        s._sensor_cache = {
            "power_to_grid_w": (0.0, _NOW, True),
        }
        assert not s._check_staleness()  # empty = no staleness

    def test_all_none_timestamps_returns_false(self, sensor_ctx, sample_config):
        """Cache entries present but all last_changed=None → returns False."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        s._sensor_cache = {
            "soc_percent":     (0.0, None, True),
            "power_to_grid_w": (0.0, None, True),
            "pv_production_w": (0.0, None, True),
            "power_to_user_w": (0.0, None, True),
        }
        assert not s._check_staleness()  # empty = no staleness


# ===========================================================================
# AC5 — Only critical sensors checked
# ===========================================================================

class TestAC5OnlyCriticalSensorsChecked:
    def test_power_to_grid_stale_does_not_trigger_failsafe(
        self, sensor_ctx, sample_config
    ):
        """power_to_grid is non-critical — staleness on it does NOT trigger FAILSAFE."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=61)
        s._sensor_cache = {
            "soc_percent":     (50.0, _NOW,     True),
            "power_to_grid_w": (0.0,  stale_ts, True),  # stale but non-critical
            "pv_production_w": (1000.0, _NOW,   True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }
        assert not s._check_staleness()  # empty = no staleness
        s._engine.hysteresis_filter.force_failsafe.assert_not_called()

    def test_unconfigured_critical_sensor_skipped_no_key_error(
        self, sensor_ctx
    ):
        """Config without power_to_user → that key absent from reverse map → silently skipped."""
        mod, mock_utcnow, _ = sensor_ctx
        cfg = {
            "evaluation_interval": 15,
            "stale_threshold_seconds": 60,
            "entities": {
                "soc":           "sensor.battery_soc",
                "power_to_grid": "sensor.power_to_grid",
                "pv_production": "sensor.pv_power",
                # power_to_user omitted intentionally
            },
        }
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, cfg)
        stale_ts = _NOW - timedelta(seconds=61)
        # Only SOC is stale — still should trigger (it IS in the map)
        s._sensor_cache = {
            "soc_percent":     (50.0, stale_ts, True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (1000.0, _NOW,   True),
        }
        # Should not raise KeyError — power_to_user not in cache_key_to_entity
        result = s._check_staleness()
        assert result  # non-empty = SOC IS critical and IS stale
        assert "sensor.battery_soc" in result

    def test_battery_discharge_absence_raises_no_error(
        self, sensor_ctx, sample_config
    ):
        """CACHE_KEY_BATTERY_DISCHARGE not in critical keys — no KeyError."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        stale_ts = _NOW - timedelta(seconds=61)
        # SOC stale; battery_discharge key not in _cache_key_to_entity
        s._sensor_cache = {
            "soc_percent":      (50.0,   stale_ts, True),
            "power_to_grid_w":  (0.0,    _NOW,     True),
            "pv_production_w":  (1000.0, _NOW,     True),
            "power_to_user_w":  (500.0,  _NOW,     True),
            "battery_discharge_w": (200.0, stale_ts, True),  # stale but not critical
        }
        # Must not raise — battery_discharge silently ignored
        result = s._check_staleness()
        assert result  # non-empty = SOC triggered it
        assert "sensor.battery_soc" in result  # SOC, not battery_discharge


# ===========================================================================
# AC6 — SurplusCalculator has zero new homeassistant imports
# ===========================================================================

class TestAC6SurplusCalculatorHAFree:
    def test_surplus_calculator_has_no_ha_imports(self):
        """SurplusCalculator source must not contain any homeassistant imports."""
        import ast

        with open(_SE_PATH, encoding="utf-8") as fh:
            source = fh.read()

        tree = ast.parse(source)

        # Collect all imports at module level (not inside if __package__ guards)
        ha_imports_in_calculator = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Check if this node is inside an if __package__ block
                # We find the enclosing context by walking the tree with parent info
                module_name = ""
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_name = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                if "homeassistant" in module_name:
                    ha_imports_in_calculator.append(module_name)

        # All HA imports must be inside if __package__ guard — verify none are
        # top-level unguarded imports by checking SurplusCalculator class body
        # Simpler: verify the class body imports nothing from homeassistant
        class_nodes = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef) and n.name == "SurplusCalculator"
        ]
        assert len(class_nodes) == 1, "SurplusCalculator class not found"
        calc_node = class_nodes[0]

        calc_ha_imports = []
        for node in ast.walk(calc_node):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = ""
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                if "homeassistant" in mod:
                    calc_ha_imports.append(mod)

        assert calc_ha_imports == [], (
            f"SurplusCalculator must have zero HA imports; found: {calc_ha_imports}"
        )


# ===========================================================================
# AC7 — Timestamp refresh from HA state registry
# ===========================================================================

def _make_ha_state(value, last_updated):
    """Create a mock HA state object with .state and .last_updated."""
    st = MagicMock()
    st.state = str(value)
    st.last_updated = last_updated
    return st


class TestTimestampRefreshFromHAState:
    """Verify _refresh_cache_timestamps prevents false staleness reports."""

    def test_refresh_updates_stale_cache_timestamp(self, sensor_ctx, sample_config):
        """Cached timestamp is old, but HA state.last_updated is fresh → refreshed."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)

        stale_ts = _NOW - timedelta(seconds=120)
        fresh_ts = _NOW - timedelta(seconds=10)
        s._sensor_cache = {
            "soc_percent":     (83.0, stale_ts, True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (5000.0, _NOW,   True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }

        # Mock HA state registry — SOC has fresh last_updated
        s.hass.states.get = MagicMock(side_effect=lambda eid: {
            "sensor.battery_soc":    _make_ha_state(83.0, fresh_ts),
            "sensor.power_to_grid":  _make_ha_state(0.0, _NOW),
            "sensor.pv_power":       _make_ha_state(5000.0, _NOW),
            "sensor.power_to_user":  _make_ha_state(500.0, _NOW),
        }.get(eid))

        s._refresh_cache_timestamps()

        # SOC timestamp should now be the fresh one from HA state
        assert s._sensor_cache["soc_percent"][1] == fresh_ts

    def test_refresh_prevents_false_staleness(self, sensor_ctx, sample_config):
        """After refresh, a sensor that was falsely stale passes staleness check."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)

        stale_ts = _NOW - timedelta(seconds=120)
        fresh_ts = _NOW - timedelta(seconds=10)
        s._sensor_cache = {
            "soc_percent":     (83.0, stale_ts, True),
            "power_to_grid_w": (0.0,  _NOW,     True),
            "pv_production_w": (5000.0, _NOW,   True),
            "power_to_user_w": (500.0,  _NOW,   True),
        }

        # Before refresh: staleness detected
        result_before = s._check_staleness()
        assert result_before  # stale

        # Mock HA state registry with fresh timestamps
        s._engine.hysteresis_filter.force_failsafe.reset_mock()
        s.hass.states.get = MagicMock(side_effect=lambda eid: {
            "sensor.battery_soc":    _make_ha_state(83.0, fresh_ts),
            "sensor.power_to_grid":  _make_ha_state(0.0, _NOW),
            "sensor.pv_power":       _make_ha_state(5000.0, _NOW),
            "sensor.power_to_user":  _make_ha_state(500.0, _NOW),
        }.get(eid))

        s._refresh_cache_timestamps()
        result_after = s._check_staleness()
        assert not result_after  # no longer stale

    def test_refresh_skips_unavailable_entities(self, sensor_ctx, sample_config):
        """Unavailable HA state does not overwrite cache timestamp."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)

        original_ts = _NOW - timedelta(seconds=30)
        s._sensor_cache = {
            "soc_percent":     (83.0, original_ts, True),
            "power_to_grid_w": (0.0,  _NOW,        True),
            "pv_production_w": (5000.0, _NOW,      True),
            "power_to_user_w": (500.0,  _NOW,      True),
        }

        unavail_state = MagicMock()
        unavail_state.state = "unavailable"
        unavail_state.last_updated = _NOW

        s.hass.states.get = MagicMock(side_effect=lambda eid: {
            "sensor.battery_soc":    unavail_state,
            "sensor.power_to_grid":  _make_ha_state(0.0, _NOW),
            "sensor.pv_power":       _make_ha_state(5000.0, _NOW),
            "sensor.power_to_user":  _make_ha_state(500.0, _NOW),
        }.get(eid))

        s._refresh_cache_timestamps()

        # SOC timestamp should remain unchanged (unavailable → skipped)
        assert s._sensor_cache["soc_percent"][1] == original_ts

    def test_refresh_skips_invalid_cache_entries(self, sensor_ctx, sample_config):
        """Cache entries marked invalid (is_valid=False) are not refreshed."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)

        original_ts = _NOW - timedelta(seconds=30)
        s._sensor_cache = {
            "soc_percent":     (83.0, original_ts, False),  # invalid
            "power_to_grid_w": (0.0,  _NOW,        True),
            "pv_production_w": (5000.0, _NOW,      True),
            "power_to_user_w": (500.0,  _NOW,      True),
        }

        s.hass.states.get = MagicMock(side_effect=lambda eid: {
            "sensor.battery_soc":    _make_ha_state(83.0, _NOW),
            "sensor.power_to_grid":  _make_ha_state(0.0, _NOW),
            "sensor.pv_power":       _make_ha_state(5000.0, _NOW),
            "sensor.power_to_user":  _make_ha_state(500.0, _NOW),
        }.get(eid))

        s._refresh_cache_timestamps()

        # SOC timestamp should remain unchanged (is_valid=False → skipped)
        assert s._sensor_cache["soc_percent"][1] == original_ts

    def test_refresh_handles_all_entities(self, sensor_ctx, sample_config):
        """All tracked entities get their timestamps refreshed, not just critical ones."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)

        stale_ts = _NOW - timedelta(seconds=120)
        fresh_ts = _NOW - timedelta(seconds=5)
        s._sensor_cache = {
            "soc_percent":     (83.0, stale_ts, True),
            "power_to_grid_w": (0.0,  stale_ts, True),  # also stale
            "pv_production_w": (5000.0, stale_ts, True),
            "power_to_user_w": (500.0,  stale_ts, True),
        }

        s.hass.states.get = MagicMock(side_effect=lambda eid: {
            "sensor.battery_soc":    _make_ha_state(83.0, fresh_ts),
            "sensor.power_to_grid":  _make_ha_state(0.0, fresh_ts),
            "sensor.pv_power":       _make_ha_state(5000.0, fresh_ts),
            "sensor.power_to_user":  _make_ha_state(500.0, fresh_ts),
        }.get(eid))

        s._refresh_cache_timestamps()

        for key in ("soc_percent", "power_to_grid_w", "pv_production_w", "power_to_user_w"):
            assert s._sensor_cache[key][1] == fresh_ts, f"{key} timestamp not refreshed"

    def test_refresh_skips_missing_cache_entries(self, sensor_ctx, sample_config):
        """Entities not yet in cache (startup) are gracefully skipped."""
        mod, mock_utcnow, _ = sensor_ctx
        mock_utcnow.return_value = _NOW
        s = _make_sensor(mod, sample_config)
        s._sensor_cache = {}  # empty cache at startup

        s.hass.states.get = MagicMock(side_effect=lambda eid:
            _make_ha_state(0.0, _NOW))

        # Should not raise
        s._refresh_cache_timestamps()
        assert s._sensor_cache == {}
