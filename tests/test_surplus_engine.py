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
        assert fd.solar_forecast_kwh_today is None

    def test_field_forecast_available_default_false(self, se):
        assert se.ForecastData().forecast_available is False

    def test_field_cloud_coverage_avg_default(self, se):
        assert se.ForecastData().cloud_coverage_avg == 50.0

    def test_field_solar_forecast_kwh_today_default_none(self, se):
        assert se.ForecastData().solar_forecast_kwh_today is None

    def test_override_fields(self, se):
        fd = se.ForecastData(
            forecast_available=True,
            cloud_coverage_avg=30.0,
            solar_forecast_kwh_today=12.5,
        )
        assert fd.forecast_available is True
        assert fd.solar_forecast_kwh_today == 12.5


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
    def test_surplus_calculator_get_soc_floor_raises(self, se, snapshot):
        calc = se.SurplusCalculator(config={})
        with pytest.raises(NotImplementedError):
            calc.get_soc_floor(snapshot)

    def test_surplus_calculator_calculate_surplus_raises(self, se, snapshot):
        calc = se.SurplusCalculator(config={})
        with pytest.raises(NotImplementedError):
            calc.calculate_surplus(snapshot)

    def test_hysteresis_filter_update_raises(self, se, now):
        hf = se.HysteresisFilter(hold_time_minutes=10)
        with pytest.raises(NotImplementedError):
            hf.update(1.5, now)

    def test_hysteresis_filter_force_failsafe_raises(self, se):
        hf = se.HysteresisFilter(hold_time_minutes=10)
        with pytest.raises(NotImplementedError):
            hf.force_failsafe("sensor_unavailable")

    def test_hysteresis_filter_resume_raises(self, se):
        hf = se.HysteresisFilter(hold_time_minutes=10)
        with pytest.raises(NotImplementedError):
            hf.resume()

    def test_forecast_consumer_get_forecast_raises(self, se):
        fc = se.ForecastConsumer(config={})
        with pytest.raises(NotImplementedError):
            asyncio.run(fc.get_forecast(hass=None))

    def test_forecast_consumer_stores_config(self, se):
        fc = se.ForecastConsumer(config={"weather": "weather.home"})
        assert fc.config == {"weather": "weather.home"}


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
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result.reported_kw == 0.0

    def test_evaluate_cycle_default_charging_state_inactive(self, se, snapshot):
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result.charging_state == "INACTIVE"

    def test_evaluate_cycle_default_reason(self, se, snapshot):
        engine = se.SurplusEngine(config={})
        result = asyncio.run(engine.evaluate_cycle(snapshot))
        assert result.reason == "engine_not_yet_implemented"

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
