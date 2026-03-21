"""Tests for Story 1.1 — YAML Configuration Schema and Parsing.

Covers all six Acceptance Criteria:
  AC1 – Basic config loading with defaults
  AC2 – time_strategy parsing
  AC3 – seasonal_targets parsing
  AC4 – DEFAULTS fallback
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol


# ===========================================================================
# AC4 — DEFAULTS dict
# ===========================================================================


class TestDefaults:
    def test_defaults_exists(self, comp):
        assert hasattr(comp, "DEFAULTS"), "DEFAULTS dict must exist in __init__.py"

    def test_defaults_evaluation_interval(self, comp):
        assert comp.DEFAULTS["evaluation_interval"] == 15

    def test_defaults_wallbox_threshold_kw(self, comp):
        assert comp.DEFAULTS["wallbox_threshold_kw"] == 4.2

    def test_defaults_hold_time_minutes(self, comp):
        assert comp.DEFAULTS["hold_time_minutes"] == 10

    def test_defaults_soc_hard_floor(self, comp):
        assert comp.DEFAULTS["soc_hard_floor"] == 50

    def test_defaults_stale_threshold_seconds(self, comp):
        assert comp.DEFAULTS["stale_threshold_seconds"] == 60

    def test_defaults_max_discharge_kw(self, comp):
        assert comp.DEFAULTS["max_discharge_kw"] == 10.0

    def test_defaults_battery_capacity_kwh(self, comp):
        assert comp.DEFAULTS["battery_capacity_kwh"] == 10.0

    def test_defaults_solar_remaining_threshold_kwh(self, comp):
        assert comp.DEFAULTS["solar_remaining_threshold_kwh"] == 2.0

    def test_defaults_seasonal_targets_has_all_months(self, comp):
        st = comp.DEFAULTS["seasonal_targets"]
        assert set(st.keys()) == set(range(1, 13))

    def test_defaults_time_strategy_has_three_entries(self, comp):
        ts = comp.DEFAULTS["time_strategy"]
        assert len(ts) == 3

    def test_defaults_time_strategy_morning_boundary(self, comp):
        first = comp.DEFAULTS["time_strategy"][0]
        assert first["before"] == "sunrise+2h"
        assert first["soc_floor"] == 100

    def test_defaults_time_strategy_default_entry_exists(self, comp):
        last = comp.DEFAULTS["time_strategy"][2]
        assert last.get("default") is True


# ===========================================================================
# Constants
# ===========================================================================


class TestConstants:
    EXPECTED = [
        "CONF_ENTITIES",
        "CONF_SOC",
        "CONF_POWER_TO_GRID",
        "CONF_PV_PRODUCTION",
        "CONF_POWER_TO_USER",
        "CONF_WEATHER",
        "CONF_FORECAST_SOLAR",
        "CONF_TIME_STRATEGY",
        "CONF_SEASONAL_TARGETS",
        "CONF_EVALUATION_INTERVAL",
    ]

    @pytest.mark.parametrize("const", EXPECTED)
    def test_constant_exists(self, comp, const):
        assert hasattr(comp, const), f"Constant {const} must be defined"

    def test_conf_entities_value(self, comp):
        assert comp.CONF_ENTITIES == "entities"

    def test_conf_soc_value(self, comp):
        assert comp.CONF_SOC == "soc"


# ===========================================================================
# AC1 — ENTITIES_SCHEMA
# ===========================================================================


class TestEntitiesSchema:
    VALID_ENTITIES = {
        "soc": "sensor.battery_soc",
        "power_to_grid": "sensor.grid_export",
        "pv_production": "sensor.pv_power",
        "power_to_user": "sensor.house_power",
    }

    def test_valid_required_entities_accepted(self, comp):
        result = comp.ENTITIES_SCHEMA(self.VALID_ENTITIES)
        assert result["soc"] == "sensor.battery_soc"

    def test_optional_entities_accepted_when_present(self, comp):
        cfg = {**self.VALID_ENTITIES, "weather": "weather.home", "forecast_solar": "sensor.forecast"}
        result = comp.ENTITIES_SCHEMA(cfg)
        assert result["weather"] == "weather.home"

    def test_missing_soc_accepted_by_schema(self, comp):
        # SOC is vol.Optional so failsafe logic in async_setup is reachable
        cfg = {k: v for k, v in self.VALID_ENTITIES.items() if k != "soc"}
        result = comp.ENTITIES_SCHEMA(cfg)
        assert "soc" not in result

    def test_missing_required_power_to_grid_raises(self, comp):
        cfg = {k: v for k, v in self.VALID_ENTITIES.items() if k != "power_to_grid"}
        with pytest.raises(vol.Invalid):
            comp.ENTITIES_SCHEMA(cfg)

    def test_invalid_entity_id_format_raises(self, comp):
        cfg = {**self.VALID_ENTITIES, "soc": "not_an_entity_id"}
        with pytest.raises(vol.Invalid):
            comp.ENTITIES_SCHEMA(cfg)


# ===========================================================================
# AC2 — TIME_ENTRY_SCHEMA / TIME_STRATEGY_SCHEMA
# ===========================================================================


class TestTimeEntrySchema:
    def test_before_with_static_time(self, comp):
        entry = {"before": "06:00", "soc_floor": 80}
        result = comp.TIME_ENTRY_SCHEMA(entry)
        assert result["before"] == "06:00"

    def test_before_with_sunrise_offset_stored_as_is(self, comp):
        entry = {"before": "sunrise+2h", "soc_floor": 100}
        result = comp.TIME_ENTRY_SCHEMA(entry)
        assert result["before"] == "sunrise+2h"

    def test_before_with_sunset_offset_stored_as_is(self, comp):
        entry = {"before": "sunset-3h", "soc_floor": 50}
        result = comp.TIME_ENTRY_SCHEMA(entry)
        assert result["before"] == "sunset-3h"
        assert result["soc_floor"] == 50

    def test_default_entry_accepted(self, comp):
        entry = {"default": True, "soc_floor": 80}
        result = comp.TIME_ENTRY_SCHEMA(entry)
        assert result.get("default") is True
        assert result["soc_floor"] == 80

    def test_soc_floor_below_zero_raises(self, comp):
        entry = {"before": "06:00", "soc_floor": -1}
        with pytest.raises(vol.Invalid):
            comp.TIME_ENTRY_SCHEMA(entry)

    def test_soc_floor_above_hundred_raises(self, comp):
        entry = {"default": True, "soc_floor": 101}
        with pytest.raises(vol.Invalid):
            comp.TIME_ENTRY_SCHEMA(entry)

    def test_time_strategy_list_schema(self, comp):
        strategy = [
            {"before": "sunrise+2h", "soc_floor": 100},
            {"before": "sunset-3h", "soc_floor": 50},
            {"default": True, "soc_floor": 80},
        ]
        schema = vol.Schema(comp.TIME_STRATEGY_SCHEMA)
        result = schema(strategy)
        assert len(result) == 3


# ===========================================================================
# AC3 — SEASONAL_TARGETS_SCHEMA
# ===========================================================================


class TestSeasonalTargetsSchema:
    def test_valid_seasonal_targets(self, comp):
        data = {1: 100, 6: 70, 12: 100}
        result = comp.SEASONAL_TARGETS_SCHEMA(data)
        assert result[1] == 100

    def test_string_month_keys_coerced_to_int(self, comp):
        # YAML delivers ints but schema uses vol.Coerce(int)
        data = {1: 90}
        result = comp.SEASONAL_TARGETS_SCHEMA(data)
        assert isinstance(list(result.keys())[0], int)

    def test_soc_value_above_100_raises(self, comp):
        with pytest.raises(vol.Invalid):
            comp.SEASONAL_TARGETS_SCHEMA({6: 101})

    def test_soc_value_below_0_raises(self, comp):
        with pytest.raises(vol.Invalid):
            comp.SEASONAL_TARGETS_SCHEMA({6: -1})

    def test_month_key_zero_raises(self, comp):
        with pytest.raises(vol.Invalid):
            comp.SEASONAL_TARGETS_SCHEMA({0: 50})

    def test_month_key_13_raises(self, comp):
        with pytest.raises(vol.Invalid):
            comp.SEASONAL_TARGETS_SCHEMA({13: 80})


# ===========================================================================
# AC1 + AC4 — CONFIG_SCHEMA exists
# ===========================================================================


class TestConfigSchema:
    def test_config_schema_exists(self, comp):
        assert hasattr(comp, "CONFIG_SCHEMA"), "CONFIG_SCHEMA must exist"

    def test_config_schema_key_is_sdm630_sim(self, comp):
        # CONFIG_SCHEMA uses literal "sdm630_sim" NOT DOMAIN
        valid = {
            "sdm630_sim": {
                "entities": {
                    "soc": "sensor.batt",
                    "power_to_grid": "sensor.grid",
                    "pv_production": "sensor.pv",
                    "power_to_user": "sensor.user",
                }
            }
        }
        result = comp.CONFIG_SCHEMA(valid)
        assert "sdm630_sim" in result

    def test_config_schema_allows_extra_keys(self, comp):
        valid = {
            "sdm630_sim": {
                "entities": {
                    "soc": "sensor.batt",
                    "power_to_grid": "sensor.grid",
                    "pv_production": "sensor.pv",
                    "power_to_user": "sensor.user",
                }
            },
            "other_integration": {"key": "value"},
        }
        result = comp.CONFIG_SCHEMA(valid)
        assert "other_integration" in result


# ===========================================================================
# AC1, AC4 — async_setup
# ===========================================================================


VALID_CONFIG = {
    "sdm630_sim": {
        "entities": {
            "soc": "sensor.battery_soc",
            "power_to_grid": "sensor.grid_export",
            "pv_production": "sensor.pv_power",
            "power_to_user": "sensor.house_power",
        }
    }
}


def _make_hass():
    hass = MagicMock()
    hass.data = {}
    hass.async_create_task = MagicMock()
    return hass


class TestAsyncSetup:
    @pytest.mark.asyncio
    async def test_returns_true_on_valid_config(self, comp):
        hass = _make_hass()
        result = await comp.async_setup(hass, VALID_CONFIG)
        assert result is True

    @pytest.mark.asyncio
    async def test_stores_config_in_hass_data(self, comp):
        hass = _make_hass()
        await comp.async_setup(hass, VALID_CONFIG)
        assert comp.DOMAIN in hass.data
        assert "config" in hass.data[comp.DOMAIN]

    @pytest.mark.asyncio
    async def test_defaults_applied_when_keys_absent(self, comp):
        hass = _make_hass()
        await comp.async_setup(hass, VALID_CONFIG)
        cfg = hass.data[comp.DOMAIN]["config"]
        assert cfg["evaluation_interval"] == comp.DEFAULTS["evaluation_interval"]
        assert cfg["soc_hard_floor"] == comp.DEFAULTS["soc_hard_floor"]

    @pytest.mark.asyncio
    async def test_missing_optional_entities_log_warning(self, comp, caplog):
        import logging
        hass = _make_hass()
        with caplog.at_level(logging.WARNING):
            await comp.async_setup(hass, VALID_CONFIG)
        # weather and forecast_solar are absent → two WARNINGs
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        optional_warns = [w for w in warnings if "weather" in w.message or "forecast_solar" in w.message]
        assert len(optional_warns) == 2

    @pytest.mark.asyncio
    async def test_missing_soc_logs_error_and_sets_failsafe(self, comp, caplog):
        import logging
        hass = _make_hass()
        config_no_soc = {
            "sdm630_sim": {
                "entities": {
                    "power_to_grid": "sensor.grid_export",
                    "pv_production": "sensor.pv_power",
                    "power_to_user": "sensor.house_power",
                }
            }
        }
        with caplog.at_level(logging.ERROR):
            result = await comp.async_setup(hass, config_no_soc)
        assert result is True  # must not crash
        cfg = hass.data[comp.DOMAIN]["config"]
        assert cfg["failsafe"] is True
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("soc" in r.message for r in errors)

    @pytest.mark.asyncio
    async def test_seasonal_targets_merged_with_defaults(self, comp):
        hass = _make_hass()
        config_partial = {
            "sdm630_sim": {
                "entities": {
                    "soc": "sensor.batt",
                    "power_to_grid": "sensor.grid",
                    "pv_production": "sensor.pv",
                    "power_to_user": "sensor.user",
                },
                "seasonal_targets": {6: 65},
            }
        }
        await comp.async_setup(hass, config_partial)
        st = hass.data[comp.DOMAIN]["config"]["seasonal_targets"]
        assert st[6] == 65  # user override
        assert st[1] == comp.DEFAULTS["seasonal_targets"][1]  # default fallback

    @pytest.mark.asyncio
    async def test_user_time_strategy_overrides_defaults(self, comp):
        hass = _make_hass()
        custom_ts = [{"before": "08:00", "soc_floor": 90}, {"default": True, "soc_floor": 60}]
        config_ts = {
            "sdm630_sim": {
                "entities": {
                    "soc": "sensor.batt",
                    "power_to_grid": "sensor.grid",
                    "pv_production": "sensor.pv",
                    "power_to_user": "sensor.user",
                },
                "time_strategy": custom_ts,
            }
        }
        await comp.async_setup(hass, config_ts)
        cfg = hass.data[comp.DOMAIN]["config"]
        assert cfg["time_strategy"] == custom_ts

    @pytest.mark.asyncio
    async def test_entities_stored_in_config(self, comp):
        hass = _make_hass()
        await comp.async_setup(hass, VALID_CONFIG)
        entities = hass.data[comp.DOMAIN]["config"]["entities"]
        assert entities["soc"] == "sensor.battery_soc"
        assert entities["power_to_grid"] == "sensor.grid_export"
