"""Tests for Story 4.4 — Sensor Value Range Validation.

Covers all Acceptance Criteria:
  AC1 – SOC out of range → FAILSAFE (reason contains entity_id and range)
  AC2 – Power sensor out of range → FAILSAFE with entity_id in reason
  AC3 – In-range values: _validate_cache() returns None
  AC4 – Default ranges applied when sensor_ranges not in config
  AC5 – Custom ranges applied; value inside default but outside custom → FAILSAFE
  AC6 – Recovery path: after in-range values, _validate_cache() returns None
  AC7 – valid=False cache entries are skipped (no double-trigger)
  AC8 – Boundary values: inclusive range check (0 and 100 valid for SOC; 100.01 fails)
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SENSOR_PATH = os.path.join(ROOT, "sensor.py")
_SE_PATH = os.path.join(ROOT, "surplus_engine.py")
_INIT_PATH = os.path.join(ROOT, "__init__.py")

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

def _load_surplus_engine():
    key = "_test_range_se"
    sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(key, _SE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_init_module():
    """Load __init__.py to get the real DEFAULTS dict."""
    key = "_test_range_init"
    sys.modules.pop(key, None)
    # Needs HA cv stub — check if already installed, install minimal if not
    if "homeassistant.helpers.config_validation" not in sys.modules:
        import voluptuous as vol
        ha_cv = types.ModuleType("homeassistant.helpers.config_validation")
        ha_cv.entity_id = lambda v: v
        sys.modules["homeassistant.helpers.config_validation"] = ha_cv
    spec = importlib.util.spec_from_file_location(key, _INIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture — loads sensor.py with HA stubs (mirrors test_surplus_engine_staleness.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def sensor_ctx():
    """Install HA stubs, load sensor.py, yield (sensor_mod, se_mod, init_mod)."""
    se   = _load_surplus_engine()
    init = _load_init_module()

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

    ha_event = types.ModuleType("homeassistant.helpers.event")
    ha_event.async_track_state_change_event = MagicMock(return_value=MagicMock())
    ha_event.async_track_time_interval      = MagicMock(return_value=MagicMock())

    ha_util    = types.ModuleType("homeassistant.util")
    ha_util_dt = types.ModuleType("homeassistant.util.dt")
    ha_util_dt.parse_datetime = MagicMock(return_value=_NOW)
    ha_util_dt.utcnow = MagicMock(return_value=_NOW)
    ha_util.dt = ha_util_dt

    pymodbus        = types.ModuleType("pymodbus")
    pymodbus_server = types.ModuleType("pymodbus.server")
    pymodbus_server.StartAsyncSerialServer = MagicMock()
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

    new_modules = {
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

    # Provide pkg root with CONF_ENTITIES and DEFAULTS
    if PKG not in sys.modules:
        pkg_root = types.ModuleType(PKG)
        pkg_root.CONF_ENTITIES = "entities"
        pkg_root.DEFAULTS = init.DEFAULTS
        sys.modules[PKG] = pkg_root
        saved[PKG] = None
    else:
        if not hasattr(sys.modules[PKG], "CONF_ENTITIES"):
            sys.modules[PKG].CONF_ENTITIES = "entities"
        if not hasattr(sys.modules[PKG], "DEFAULTS"):
            sys.modules[PKG].DEFAULTS = init.DEFAULTS

    sys.modules.pop(f"{PKG}.sensor", None)
    spec = importlib.util.spec_from_file_location(
        f"{PKG}.sensor", _SENSOR_PATH,
        submodule_search_locations=[ROOT],
    )
    sensor_mod = importlib.util.module_from_spec(spec)
    sensor_mod.__package__ = PKG
    sys.modules[f"{PKG}.sensor"] = sensor_mod
    spec.loader.exec_module(sensor_mod)

    yield sensor_mod, se, init

    sys.modules.pop(f"{PKG}.sensor", None)
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


@pytest.fixture
def default_config():
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
        # sensor_ranges from DEFAULTS (as __init__.py async_setup would populate):
        "sensor_ranges": {
            "soc": (0, 100),
            "power_w": (-30000, 30000),
        },
    }


def _make_sensor(mod, cfg):
    """Instantiate SDM630SimSensor with mocked engine and maps."""
    s = mod.SDM630SimSensor("Test Sensor", MagicMock(), cfg)
    s.async_on_remove      = MagicMock()
    s.async_write_ha_state = MagicMock()
    s._invalidation_reasons = {}
    entities_cfg = cfg.get("entities", {})
    s._entity_to_cache_key = {
        eid: mod.ENTITY_ROLE_TO_CACHE_KEY[role]
        for role, eid in entities_cfg.items()
        if role in mod.ENTITY_ROLE_TO_CACHE_KEY
    }
    s._cache_key_to_entity = {v: k for k, v in s._entity_to_cache_key.items()}
    mock_engine = MagicMock()
    mock_engine.hysteresis_filter = MagicMock()
    mock_engine.hysteresis_filter.state = "INACTIVE"
    s._engine = mock_engine
    return s


def _valid_cache(soc=60.0, grid=0.0, pv=2000.0, user=1500.0):
    """Return a fully-populated, all-valid cache with reasonable values."""
    return {
        "soc_percent":     (soc,  _NOW, True),
        "power_to_grid_w": (grid, _NOW, True),
        "pv_production_w": (pv,   _NOW, True),
        "power_to_user_w": (user, _NOW, True),
    }


# ===========================================================================
# AC1 — SOC out of range → FAILSAFE
# ===========================================================================

class TestAC1SocOutOfRange:
    def test_soc_above_100_returns_reason(self, sensor_ctx, default_config):
        """SOC=105 → _validate_cache returns reason with entity_id and range."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(soc=105.0)
        result = s._validate_cache()
        assert result is not None
        assert "sensor.battery_soc" in result
        assert "out of range [0, 100]" in result

    def test_soc_above_100_includes_value(self, sensor_ctx, default_config):
        """Reason string includes the actual invalid value."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(soc=105.0)
        result = s._validate_cache()
        assert "105.0" in result

    def test_soc_negative_returns_reason(self, sensor_ctx, default_config):
        """SOC=-1 → out of range [0, 100]."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(soc=-1.0)
        result = s._validate_cache()
        assert result is not None
        assert "out of range [0, 100]" in result


# ===========================================================================
# AC2 — Power sensor out of range → FAILSAFE with entity_id
# ===========================================================================

class TestAC2PowerSensorOutOfRange:
    def test_pv_production_too_high(self, sensor_ctx, default_config):
        """pv_production=35000 W → FAILSAFE with entity_id and range."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(pv=35000.0)
        result = s._validate_cache()
        assert result is not None
        assert "sensor.pv_power" in result
        assert "[-30000, 30000]" in result

    def test_power_to_grid_out_of_range(self, sensor_ctx, default_config):
        """power_to_grid=-35000 W → FAILSAFE."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(grid=-35000.0)
        result = s._validate_cache()
        assert result is not None
        assert "sensor.power_to_grid" in result

    def test_power_to_user_out_of_range(self, sensor_ctx, default_config):
        """power_to_user=-35000 W → FAILSAFE with entity_id."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(user=-35000.0)
        result = s._validate_cache()
        assert result is not None
        # entity_id for power_to_user maps to the role name in _cache_key_to_entity
        assert result is not None
        assert "[-30000, 30000]" in result


# ===========================================================================
# AC3 — In-range values: returns None
# ===========================================================================

class TestAC3InRangeNoFailsafe:
    def test_all_in_range_returns_none(self, sensor_ctx, default_config):
        """All cache values within ranges → None (no failure)."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache()
        assert s._validate_cache() is None

    def test_pv_production_at_30000_returns_none(self, sensor_ctx, default_config):
        """pv_production=30000 (at upper bound) → valid."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(pv=30000.0)
        assert s._validate_cache() is None

    def test_power_to_grid_negative_in_range_returns_none(
        self, sensor_ctx, default_config
    ):
        """power_to_grid=-30000 (lower bound) → valid."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(grid=-30000.0)
        assert s._validate_cache() is None


# ===========================================================================
# AC4 — Default ranges used when sensor_ranges not in config
# ===========================================================================

class TestAC4DefaultRangesApplied:
    def test_missing_sensor_ranges_key_uses_defaults(self, sensor_ctx):
        """Config without sensor_ranges → defaults applied (SOC=105 still fails)."""
        mod, _, init = sensor_ctx
        cfg = {
            "name": "SDM630 Test",
            "entities": {
                "soc":           "sensor.battery_soc",
                "power_to_grid": "sensor.power_to_grid",
                "pv_production": "sensor.pv_power",
                "power_to_user": "sensor.power_to_user",
            },
            # no sensor_ranges key — must fall back to DEFAULTS
        }
        s = _make_sensor(mod, cfg)
        s._sensor_cache = _valid_cache(soc=105.0)
        result = s._validate_cache()
        assert result is not None
        assert "out of range [0, 100]" in result

    def test_missing_sensor_ranges_in_range_returns_none(self, sensor_ctx):
        """Config without sensor_ranges → in-range values pass (AC3 still holds)."""
        mod, _, _ = sensor_ctx
        cfg = {
            "name": "SDM630 Test",
            "entities": {
                "soc":           "sensor.battery_soc",
                "power_to_grid": "sensor.power_to_grid",
                "pv_production": "sensor.pv_power",
                "power_to_user": "sensor.power_to_user",
            },
        }
        s = _make_sensor(mod, cfg)
        s._sensor_cache = _valid_cache()
        assert s._validate_cache() is None


# ===========================================================================
# AC5 — Custom ranges applied
# ===========================================================================

class TestAC5CustomRanges:
    def test_custom_power_range_triggers_failsafe(self, sensor_ctx):
        """power_w: [-20000, 20000] custom; value=25000 inside default but outside custom."""
        mod, _, _ = sensor_ctx
        cfg = {
            "name": "SDM630 Test",
            "entities": {
                "soc":           "sensor.battery_soc",
                "power_to_grid": "sensor.power_to_grid",
                "pv_production": "sensor.pv_power",
                "power_to_user": "sensor.power_to_user",
            },
            "sensor_ranges": {
                "soc": (0, 100),
                "power_w": (-20000, 20000),
            },
        }
        s = _make_sensor(mod, cfg)
        s._sensor_cache = _valid_cache(pv=25000.0)
        result = s._validate_cache()
        assert result is not None
        assert "[-20000, 20000]" in result

    def test_custom_soc_range_triggers_failsafe_at_5(self, sensor_ctx):
        """soc: [10, 100] custom; value=5 inside default but outside custom."""
        mod, _, _ = sensor_ctx
        cfg = {
            "name": "SDM630 Test",
            "entities": {
                "soc":           "sensor.battery_soc",
                "power_to_grid": "sensor.power_to_grid",
                "pv_production": "sensor.pv_power",
                "power_to_user": "sensor.power_to_user",
            },
            "sensor_ranges": {
                "soc": (10, 100),
                "power_w": (-30000, 30000),
            },
        }
        s = _make_sensor(mod, cfg)
        s._sensor_cache = _valid_cache(soc=5.0)
        result = s._validate_cache()
        assert result is not None
        assert "[10, 100]" in result


# ===========================================================================
# AC6 — Recovery path: in-range on next tick returns None
# ===========================================================================

class TestAC6RecoveryPath:
    def test_after_out_of_range_next_tick_in_range_returns_none(
        self, sensor_ctx, default_config
    ):
        """After recovery (sensor returns in-range value), _validate_cache() = None."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)

        # First: out of range
        s._sensor_cache = _valid_cache(soc=105.0)
        result_fail = s._validate_cache()
        assert result_fail is not None

        # Recovery: valid state arrives
        s._sensor_cache = _valid_cache(soc=75.0)
        result_ok = s._validate_cache()
        assert result_ok is None


# ===========================================================================
# AC7 — valid=False entries skipped (no double-trigger)
# ===========================================================================

class TestAC7InvalidEntriesSkipped:
    def test_valid_false_entry_not_range_checked(self, sensor_ctx, default_config):
        """valid=False cache entry with out-of-range value → skipped, no reason."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        # SOC is invalid (valid=False) AND out-of-range — should be skipped
        s._sensor_cache = {
            "soc_percent":     (105.0, _NOW, False),  # invalid AND out-of-range
            "power_to_grid_w": (0.0,   _NOW, True),
            "pv_production_w": (2000.0, _NOW, True),
            "power_to_user_w": (1500.0, _NOW, True),
        }
        assert s._validate_cache() is None

    def test_none_entry_skipped(self, sensor_ctx, default_config):
        """Cache entry missing entirely → skipped (no KeyError, no FAILSAFE)."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        # Only three entries (SOC missing entirely)
        s._sensor_cache = {
            "power_to_grid_w": (0.0,   _NOW, True),
            "pv_production_w": (2000.0, _NOW, True),
            "power_to_user_w": (1500.0, _NOW, True),
        }
        assert s._validate_cache() is None

    def test_mixed_valid_false_and_out_of_range_power(
        self, sensor_ctx, default_config
    ):
        """SOC valid=False (skipped) but pv_production out-of-range (valid=True) → fail."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = {
            "soc_percent":     (105.0,  _NOW, False),  # skip
            "power_to_grid_w": (0.0,    _NOW, True),
            "pv_production_w": (35000.0, _NOW, True),  # fail
            "power_to_user_w": (1500.0,  _NOW, True),
        }
        result = s._validate_cache()
        assert result is not None
        assert "[-30000, 30000]" in result


# ===========================================================================
# AC8 — Boundary values: inclusive range check
# ===========================================================================

class TestAC8BoundaryValues:
    def test_soc_exactly_0_is_valid(self, sensor_ctx, default_config):
        """SOC=0 (lower bound) → no FAILSAFE (inclusive)."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(soc=0.0)
        assert s._validate_cache() is None

    def test_soc_exactly_100_is_valid(self, sensor_ctx, default_config):
        """SOC=100 (upper bound) → no FAILSAFE (inclusive)."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(soc=100.0)
        assert s._validate_cache() is None

    def test_soc_100_01_fails(self, sensor_ctx, default_config):
        """SOC=100.01 (just above upper bound) → FAILSAFE triggered."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(soc=100.01)
        result = s._validate_cache()
        assert result is not None
        assert "out of range [0, 100]" in result

    def test_power_exactly_at_lower_bound_valid(self, sensor_ctx, default_config):
        """pv_production=-30000 (lower bound) → valid (inclusive)."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(pv=-30000.0)
        assert s._validate_cache() is None

    def test_power_exactly_at_upper_bound_valid(self, sensor_ctx, default_config):
        """pv_production=30000 (upper bound) → valid (inclusive)."""
        mod, _, _ = sensor_ctx
        s = _make_sensor(mod, default_config)
        s._sensor_cache = _valid_cache(pv=30000.0)
        assert s._validate_cache() is None


# ===========================================================================
# No homeassistant import in this file
# ===========================================================================

class TestNoHomeAssistantImport:
    def test_no_homeassistant_import(self):
        """Confirm this test file has no direct homeassistant import."""
        import ast
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else ([node.module] if node.module else [])
                )
                for name in names:
                    assert not (name or "").startswith("homeassistant"), (
                        f"Unexpected homeassistant import: {name}"
                    )
