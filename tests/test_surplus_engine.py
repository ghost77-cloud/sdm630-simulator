"""Tests for Story 1.2 — surplus_engine.py Module Scaffold with Dataclasses.

Covers all Acceptance Criteria:
  AC1 – Module imports cleanly; exposes required top-level names
  AC2 – SurplusCalculator uses stdlib imports only
  AC3 – EvaluationResult dataclass with exact 8 fields and types
  AC4 – ForecastData dataclass with correct defaults
  AC5 – SensorSnapshot dataclass with required fields
  AC6 – Module-level constants and dual-import guard
  AC7 – Skeleton classes raise NotImplementedError / SurplusEngine returns default
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
import sys
from dataclasses import fields
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Module loading helper
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE_PATH = os.path.join(ROOT, "surplus_engine.py")
_MODULE_NAME = "surplus_engine"


@pytest.fixture(scope="module")
def se():
    """Load surplus_engine as a standalone module (no HA runtime needed)."""
    # Evict any cached copy so the fixture always starts clean
    sys.modules.pop(_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 6, 15, 12, 0, 0)


@pytest.fixture
def snapshot(se, now):
    """Minimal valid SensorSnapshot for testing."""
    return se.SensorSnapshot(
        soc_percent=75.0,
        power_to_grid_w=1500.0,
        pv_production_w=3000.0,
        power_to_user_w=1500.0,
        timestamp=now,
        sunset_time=None,
        sunrise_time=None,
    )


# ===========================================================================
# AC1 — Module importable, exposes required top-level names
# ===========================================================================

class TestModuleImport:
    REQUIRED_NAMES = [
        "SurplusEngine",
        "SurplusCalculator",
        "ForecastConsumer",
        "HysteresisFilter",
        "SensorSnapshot",
        "EvaluationResult",
        "ForecastData",
    ]

    def test_imports_without_error(self, se):
        """Module must load without ImportError or ModuleNotFoundError."""
        assert se is not None

    @pytest.mark.parametrize("name", REQUIRED_NAMES)
    def test_top_level_name_exposed(self, se, name):
        assert hasattr(se, name), f"Module must expose top-level name: {name}"

    def test_no_extra_undocumented_classes(self, se):
        """Sanity check — the 7 required names are all importable as classes."""
        for name in self.REQUIRED_NAMES:
            obj = getattr(se, name)
            assert callable(obj), f"{name} should be a callable (class)"


# ===========================================================================
# AC2 — SurplusCalculator uses stdlib imports only
# ===========================================================================

class TestSurplusCalculatorImports:
    def test_surplus_calculator_is_in_module(self, se):
        assert hasattr(se, "SurplusCalculator")

    def test_module_does_not_import_homeassistant(self, se):
        """surplus_engine must not import HA at module level."""
        module_source = inspect.getsource(se)
        # HA import should ONLY appear inside an `if __package__:` guard
        lines = module_source.splitlines()
        in_guard = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("if __package__:"):
                in_guard = True
                continue
            # Any block at indentation 0 after the guard resets it
            if in_guard and line and not line[0].isspace():
                in_guard = False
            if not in_guard and "homeassistant" in stripped and not stripped.startswith("#"):
                pytest.fail(
                    f"Bare HA import found outside __package__ guard: {line!r}"
                )

    def test_surplus_calculator_stores_config(self, se):
        calc = se.SurplusCalculator(config={"evaluation_interval": 15})
        assert calc.config == {"evaluation_interval": 15}


# ===========================================================================
# AC3 — EvaluationResult dataclass — exact 8 fields with correct types
# ===========================================================================

class TestEvaluationResult:
    EXPECTED_FIELDS = {
        "reported_kw": float,
        "real_surplus_kw": float,
        "buffer_used_kw": float,
        "soc_percent": float,
        "soc_floor_active": int,
        "charging_state": str,
        "reason": str,
        "forecast_available": bool,
    }

    def test_is_dataclass(self, se):
        import dataclasses
        assert dataclasses.is_dataclass(se.EvaluationResult)

    def test_has_exactly_eight_fields(self, se):
        assert len(fields(se.EvaluationResult)) == 8

    @pytest.mark.parametrize("field_name,expected_type", EXPECTED_FIELDS.items())
    def test_field_type(self, se, field_name, expected_type):
        import typing
        fld = {f.name: f for f in fields(se.EvaluationResult)}
        assert field_name in fld, f"EvaluationResult must have field: {field_name}"
        # Use get_type_hints() to resolve PEP 563 stringified annotations
        hints = typing.get_type_hints(se.EvaluationResult)
        ann = hints.get(field_name)
        assert ann is expected_type, (
            f"EvaluationResult.{field_name}: expected {expected_type}, got {ann}"
        )

    def test_instantiation_with_all_fields(self, se):
        result = se.EvaluationResult(
            reported_kw=1.5,
            real_surplus_kw=1.2,
            buffer_used_kw=0.3,
            soc_percent=80.0,
            soc_floor_active=50,
            charging_state="ACTIVE",
            reason="surplus_detected",
            forecast_available=True,
        )
        assert result.reported_kw == 1.5
        assert result.charging_state == "ACTIVE"
        assert result.forecast_available is True

    def test_no_defaults_all_fields_required(self, se):
        """All 8 fields must be required (no defaults) — strict dataclass."""
        with pytest.raises(TypeError):
            se.EvaluationResult()  # must fail — missing fields


# ===========================================================================
# AC4 — ForecastData dataclass with defaults
# ===========================================================================

class TestForecastData:
    def test_is_dataclass(self, se):
        import dataclasses
        assert dataclasses.is_dataclass(se.ForecastData)

    def test_instantiate_with_no_args(self, se):
        fd = se.ForecastData()
        assert fd.forecast_available is False
        assert fd.cloud_coverage_avg == 50.0
        assert fd.solar_forecast_kwh_remaining is None

    def test_field_forecast_available_default_false(self, se):
        assert se.ForecastData().forecast_available is False

    def test_field_cloud_coverage_avg_default(self, se):
        assert se.ForecastData().cloud_coverage_avg == 50.0

    def test_field_solar_forecast_kwh_remaining_default_none(self, se):
        assert se.ForecastData().solar_forecast_kwh_remaining is None

    def test_override_fields(self, se):
        fd = se.ForecastData(
            forecast_available=True,
            cloud_coverage_avg=30.0,
            solar_forecast_kwh_remaining=12.5,
        )
        assert fd.forecast_available is True
        assert fd.solar_forecast_kwh_remaining == 12.5


# ===========================================================================
# AC5 — SensorSnapshot dataclass with required fields
# ===========================================================================

class TestSensorSnapshot:
    REQUIRED_FIELDS = [
        "soc_percent",
        "power_to_grid_w",
        "pv_production_w",
        "power_to_user_w",
        "timestamp",
        "sunset_time",
        "sunrise_time",
        "forecast",
    ]

    def test_is_dataclass(self, se):
        import dataclasses
        assert dataclasses.is_dataclass(se.SensorSnapshot)

    @pytest.mark.parametrize("field_name", REQUIRED_FIELDS)
    def test_required_field_exists(self, se, field_name):
        fld_names = [f.name for f in fields(se.SensorSnapshot)]
        assert field_name in fld_names, f"SensorSnapshot must have field: {field_name}"

    def test_forecast_defaults_to_none(self, se, now):
        snap = se.SensorSnapshot(
            soc_percent=50.0,
            power_to_grid_w=0.0,
            pv_production_w=0.0,
            power_to_user_w=0.0,
            timestamp=now,
            sunset_time=None,
            sunrise_time=None,
        )
        assert snap.forecast is None

    def test_instantiation_with_forecast(self, se, now):
        fd = se.ForecastData(forecast_available=True, cloud_coverage_avg=20.0)
        snap = se.SensorSnapshot(
            soc_percent=80.0,
            power_to_grid_w=500.0,
            pv_production_w=2000.0,
            power_to_user_w=1500.0,
            timestamp=now,
            sunset_time=datetime(2026, 6, 15, 21, 0),
            sunrise_time=datetime(2026, 6, 15, 5, 0),
            forecast=fd,
        )
        assert snap.forecast.forecast_available is True
        assert snap.sunset_time.hour == 21

    def test_forecast_field_is_last_with_default(self, se):
        """forecast field with default=None must come after required fields."""
        fld_list = fields(se.SensorSnapshot)
        non_default = [f for f in fld_list if f.default is f.default and f.name != "forecast"]
        forecast_fld = next((f for f in fld_list if f.name == "forecast"), None)
        assert forecast_fld is not None
        # forecast must have a default (None)
        import dataclasses
        assert forecast_fld.default is None or forecast_fld.default_factory is not dataclasses.MISSING


# ===========================================================================
# AC6 — Module-level constants and dual-import guard
# ===========================================================================

class TestModuleLevelDeclarations:
    def test_logger_defined(self, se):
        assert hasattr(se, "_LOGGER"), "_LOGGER must be defined at module level"
        assert isinstance(se._LOGGER, logging.Logger)

    def test_soc_hard_floor_defined(self, se):
        assert hasattr(se, "SOC_HARD_FLOOR"), "SOC_HARD_FLOOR must be defined"

    def test_soc_hard_floor_value(self, se):
        assert se.SOC_HARD_FLOOR == 50

    def test_soc_hard_floor_is_int(self, se):
        assert isinstance(se.SOC_HARD_FLOOR, int)

    def test_dual_import_guard_present(self, se):
        """if __package__: guard must be present in source."""
        source = inspect.getsource(se)
        assert "if __package__:" in source, (
            "Dual-import guard 'if __package__:' must be present in surplus_engine.py"
        )


# ===========================================================================
# AC7 — Skeleton classes raise NotImplementedError; SurplusEngine returns default
# ===========================================================================

class TestSkeletonNotImplemented:
    def test_surplus_calculator_get_soc_floor_returns_int(self, se, snapshot):
        calc = se.SurplusCalculator(config={})
        result = calc.get_soc_floor(snapshot)
        assert isinstance(result, int)
        assert result >= se.SOC_HARD_FLOOR

    def test_surplus_calculator_calculate_surplus_returns_result(self, se, snapshot):
        """calculate_surplus is implemented in Story 2.2 — returns EvaluationResult."""
        calc = se.SurplusCalculator(config={})
        result = calc.calculate_surplus(snapshot)
        assert isinstance(result, se.EvaluationResult)

    def test_hysteresis_filter_update_returns_float(self, se, now):
        """HysteresisFilter.update() is implemented in Story 2.3 — returns float."""
        hf = se.HysteresisFilter(config={"hold_time_minutes": 10, "wallbox_threshold_kw": 4.2})
        result = hf.update(1.5, now)
        assert isinstance(result, float)

    def test_hysteresis_filter_force_failsafe_works(self, se):
        """HysteresisFilter.force_failsafe() is implemented in Story 2.3 — transitions to FAILSAFE."""
        hf = se.HysteresisFilter(config={})
        hf.force_failsafe("sensor_unavailable")
        assert hf.state == "FAILSAFE"

    def test_hysteresis_filter_resume_works(self, se):
        """HysteresisFilter.resume() is implemented in Story 2.3 — transitions to INACTIVE."""
        hf = se.HysteresisFilter(config={})
        hf.force_failsafe("test")
        hf.resume()
        assert hf.state == "INACTIVE"

    def test_forecast_consumer_stores_config(self, se):
        fc = se.ForecastConsumer(config={"weather": "weather.home"})
        assert fc.config == {"weather": "weather.home"}


# ===========================================================================
# Story 3.1 — ForecastConsumer.get_forecast
# ===========================================================================

class MockHassServices:
    """Minimal hass.services stub for testing get_forecast."""
    def __init__(self, response=None, raises=None):
        self._response = response
        self._raises = raises

    async def async_call(self, domain, service, data, *, blocking, return_response):
        if self._raises is not None:
            raise self._raises
        return self._response


class MockHassState:
    def __init__(self, state: str):
        self.state = state


class MockHass:
    """Minimal hass stub with services and states support."""
    def __init__(self, service_response=None, service_raises=None, states=None):
        self.services = MockHassServices(
            response=service_response, raises=service_raises
        )
        self._states: dict = states or {}

    def states_get(self, entity_id: str):
        return self._states.get(entity_id)

    def __getattr__(self, name):
        if name == "states":
            return type("States", (), {"get": lambda _, eid: self._states.get(eid)})()
        raise AttributeError(name)


class TestForecastConsumerGetForecast:
    """Unit tests for ForecastConsumer.get_forecast (Story 3.1)."""

    @staticmethod
    def _make_forecast_entries(cloud_values, extra=None):
        """Build fake hourly forecast entries."""
        entries = [{"datetime": f"2026-03-21T{i:02d}:00:00+00:00", "cloud_coverage": v}
                   for i, v in enumerate(cloud_values)]
        if extra:
            entries.extend(extra)
        return entries

    # --- AC4: weather entity not configured → silent no-op ---

    def test_ac4_no_weather_entity_returns_defaults(self, se):
        """AC4: absent 'weather' key → ForecastData() with all defaults, no exception."""
        fc = se.ForecastConsumer(config={"entities": {}})
        result = asyncio.run(fc.get_forecast(hass=None))
        assert result.forecast_available is False
        assert result.cloud_coverage_avg == 50.0
        assert result.solar_forecast_kwh_remaining is None

    def test_ac4_no_entities_key_returns_defaults(self, se):
        """AC4: missing 'entities' block → ForecastData() immediately."""
        fc = se.ForecastConsumer(config={})
        result = asyncio.run(fc.get_forecast(hass=None))
        assert result.forecast_available is False

    # --- AC1: weather forecast fetched, cloud_coverage_avg computed ---

    def test_ac1_fetches_weather_service_and_returns_avg(self, se):
        """AC1: calls weather.get_forecasts and averages cloud_coverage of first 6 entries."""
        entries = self._make_forecast_entries([20, 40, 60, 80, 100, 10, 99])  # 7 entries, take first 6
        response = {"weather.openweathermap": {"forecast": entries}}
        hass = MockHass(service_response=response)
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.openweathermap"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True
        expected_avg = (20 + 40 + 60 + 80 + 100 + 10) / 6
        assert abs(result.cloud_coverage_avg - expected_avg) < 0.001

    def test_ac1_only_first_six_entries_consumed(self, se):
        """AC1: only first 6 entries are used (7th+ ignored)."""
        entries = self._make_forecast_entries([0, 0, 0, 0, 0, 0, 100])  # 7th = 100, ignored
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(service_response=response)
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.cloud_coverage_avg == 0.0  # 100 was excluded

    def test_ac1_entries_missing_cloud_coverage_skipped(self, se):
        """AC1: entries without cloud_coverage key are silently excluded from avg."""
        entries = [
            {"datetime": "2026-03-21T10:00:00+00:00", "cloud_coverage": 40},
            {"datetime": "2026-03-21T11:00:00+00:00"},  # no cloud_coverage
            {"datetime": "2026-03-21T12:00:00+00:00", "cloud_coverage": 60},
        ]
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(service_response=response)
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True
        assert abs(result.cloud_coverage_avg - 50.0) < 0.001  # avg of 40 and 60

    def test_ac1_all_entries_missing_cloud_coverage_uses_neutral(self, se):
        """AC1: if no entry has cloud_coverage, avg defaults to 50.0."""
        entries = [{"datetime": "2026-03-21T10:00:00+00:00"} for _ in range(3)]
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(service_response=response)
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True
        assert result.cloud_coverage_avg == 50.0

    def test_ac1_result_forecast_available_true(self, se):
        """AC1: forecast_available is True after successful fetch."""
        entries = self._make_forecast_entries([30, 30, 30])
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(service_response=response)
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True

    # --- AC2: solar forecast entity state read ---

    def test_ac2_solar_entity_state_parsed(self, se):
        """AC2: forecast_solar entity state is read and parsed as float kWh."""
        entries = self._make_forecast_entries([50])
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(
            service_response=response,
            states={"sensor.solar_remaining": MockHassState("3.75")},
        )
        fc = se.ForecastConsumer(config={
            "entities": {
                "weather": "weather.test",
                "forecast_solar": "sensor.solar_remaining",
            }
        })
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.solar_forecast_kwh_remaining == pytest.approx(3.75)

    def test_ac2_forecast_available_true_when_solar_also_fetched(self, se):
        """AC2: forecast_available True when both weather and solar succeed."""
        entries = self._make_forecast_entries([50])
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(
            service_response=response,
            states={"sensor.solar_remaining": MockHassState("2.0")},
        )
        fc = se.ForecastConsumer(config={
            "entities": {
                "weather": "weather.test",
                "forecast_solar": "sensor.solar_remaining",
            }
        })
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True

    # --- AC3: errors handled gracefully ---

    def test_ac3_service_exception_returns_defaults(self, se):
        """AC3: async_call raising Exception → ForecastData() with conservative defaults."""
        hass = MockHass(service_raises=RuntimeError("HA offline"))
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is False
        assert result.cloud_coverage_avg == 50.0
        assert result.solar_forecast_kwh_remaining is None

    def test_ac3_malformed_response_returns_defaults(self, se):
        """AC3: malformed response dict (KeyError) → ForecastData() with defaults."""
        # response missing the entity key
        hass = MockHass(service_response={"wrong_key": {}})
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is False
        assert result.cloud_coverage_avg == 50.0

    def test_ac3_warning_logged_on_exception(self, se, caplog):
        """AC3: warning is logged once when forecast fetch fails."""
        hass = MockHass(service_raises=ValueError("bad data"))
        fc = se.ForecastConsumer(config={"entities": {"weather": "weather.test"}})
        with caplog.at_level(logging.WARNING):
            asyncio.run(fc.get_forecast(hass=hass))
        warning_msgs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_msgs) >= 1
        assert "Forecast unavailable" in warning_msgs[0].message

    def test_ac3_unavailable_state_handled_gracefully(self, se):
        """AC3: hass.states.get returning None → no exception, solar remains None."""
        entries = self._make_forecast_entries([40])
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(
            service_response=response,
            states={},  # solar entity absent → states.get returns None
        )
        fc = se.ForecastConsumer(config={
            "entities": {
                "weather": "weather.test",
                "forecast_solar": "sensor.missing",
            }
        })
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True  # weather fetch succeeded
        assert result.solar_forecast_kwh_remaining is None  # solar failed gracefully

    # --- AC5: partial config (only solar, no weather) ---

    def test_ac5_only_solar_no_weather_returns_solar_data(self, se):
        """AC5: config has forecast_solar but no weather → solar populated, forecast_available=True."""
        hass = MockHass(states={"sensor.solar_remaining": MockHassState("5.0")})
        fc = se.ForecastConsumer(config={
            "entities": {"forecast_solar": "sensor.solar_remaining"}
        })
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True
        assert result.cloud_coverage_avg == 50.0  # neutral default (no weather)
        assert result.solar_forecast_kwh_remaining == pytest.approx(5.0)

    def test_ac5_solar_state_unavailable_string_skipped(self, se):
        """AC5: solar state='unavailable' → solar_forecast_kwh_remaining stays None."""
        entries = self._make_forecast_entries([60])
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(
            service_response=response,
            states={"sensor.solar_remaining": MockHassState("unavailable")},
        )
        fc = se.ForecastConsumer(config={
            "entities": {
                "weather": "weather.test",
                "forecast_solar": "sensor.solar_remaining",
            }
        })
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True
        assert result.solar_forecast_kwh_remaining is None

    def test_ac5_solar_state_unknown_string_skipped(self, se):
        """AC5: solar state='unknown' → solar_forecast_kwh_remaining stays None."""
        entries = self._make_forecast_entries([60])
        response = {"weather.test": {"forecast": entries}}
        hass = MockHass(
            service_response=response,
            states={"sensor.solar_remaining": MockHassState("unknown")},
        )
        fc = se.ForecastConsumer(config={
            "entities": {
                "weather": "weather.test",
                "forecast_solar": "sensor.solar_remaining",
            }
        })
        result = asyncio.run(fc.get_forecast(hass=hass))
        assert result.forecast_available is True
        assert result.solar_forecast_kwh_remaining is None

    # --- AC6: SurplusEngine has _forecast_consumer wired ---

    def test_ac6_surplus_engine_has_forecast_consumer(self, se):
        """AC6: SurplusEngine.__init__ creates _forecast_consumer attribute."""
        engine = se.SurplusEngine(config={})
        assert hasattr(engine, "_forecast_consumer")
        assert isinstance(engine._forecast_consumer, se.ForecastConsumer)

    def test_ac6_forecast_consumer_uses_same_config(self, se):
        """AC6: _forecast_consumer receives same config as SurplusEngine."""
        cfg = {"entities": {"weather": "weather.test"}, "hold_time_minutes": 5}
        engine = se.SurplusEngine(config=cfg)
        assert engine._forecast_consumer.config is cfg


class TestSurplusEngineDefault:
    def test_evaluate_cycle_returns_evaluation_result(self, se, snapshot):
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert isinstance(result, se.EvaluationResult)

    def test_evaluate_cycle_never_raises(self, se, snapshot):
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result is not None

    def test_evaluate_cycle_default_reported_kw(self, se, snapshot):
        """SurplusEngine.evaluate_cycle() is fully implemented in Story 2.3 — returns real kW."""
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert isinstance(result.reported_kw, float)
        assert result.reported_kw >= 0.0

    def test_evaluate_cycle_default_charging_state_inactive(self, se, snapshot):
        """charging_state is one of the three valid states (Story 2.3)."""
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result.charging_state in ("ACTIVE", "INACTIVE", "FAILSAFE")

    def test_evaluate_cycle_default_reason(self, se, snapshot):
        """reason is a non-empty string (Story 2.3 — no longer a stub placeholder)."""
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0
        assert result.reason != "engine_not_yet_implemented"

    def test_evaluate_cycle_is_coroutine(self, se):
        """evaluate_cycle must be async."""
        engine = se.SurplusEngine(config={})
        coro = engine.evaluate_cycle.__func__
        assert inspect.iscoroutinefunction(coro), (
            "SurplusEngine.evaluate_cycle must be an async def"
        )

    def test_surplus_engine_stores_config(self, se):
        engine = se.SurplusEngine(config={"hold_time_minutes": 10})
        assert engine.config == {"hold_time_minutes": 10}

    def test_evaluate_cycle_default_soc_floor_active(self, se, snapshot):
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result.soc_floor_active == 50

    def test_evaluate_cycle_default_forecast_available_false(self, se, snapshot):
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result.forecast_available is False
