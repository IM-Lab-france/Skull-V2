"""Startup selection and readiness tests for SKULL-04.5."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from adapters import (
    AudioAdapter,
    BluetoothAdapter,
    ESP32Adapter,
    GazeAdapter,
    ServoAdapter,
    SmokeAdapter,
)
from runtime_factory import (
    ProductionAdapterProvider,
    RuntimeConfigurationError,
    build_adapters,
    resolve_runtime_mode,
    runtime_readiness,
)
from simulated_audio import SimulatedAudioPlayer
from simulated_external import (
    SimulatedBluetoothAdapter,
    SimulatedESP32Adapter,
    SimulatedSmokeAdapter,
)
from simulated_gaze import SimulatedGazeAdapter
from simulated_hardware import SimulatedHardware
from simulation_clock import SimulatedClock


class ProductionSentinel:
    """Non-simulated sentinel used to prove provider selection only."""

    def set_named_angle(self, name, deg, log_enabled=True):
        pass

    def neutral(self):
        pass

    def cleanup(self):
        pass

    def set_pitch_offset(self, servo_name, offset):
        pass

    def load(self, session_dir):
        pass

    def play(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass

    def stop(self, reason="stop"):
        pass

    def status(self):
        return {}

    def set_on_track_finished(self, callback):
        pass

    def scan(self):
        return []

    def pair(self, address):
        return {}

    def connect(self, address):
        return True

    def info(self, address):
        return None

    def request(self, path, method="GET", json_payload=None):
        return {}

    def trigger(self, session_name):
        pass

    def get_command(self):
        return None

    def stop_gaze(self, timeout=1.0):
        pass

    # GazeAdapter.stop has the same name as AudioAdapter.stop; one method is
    # sufficient for the runtime structural check.


class FakeSyncPlayer(ProductionSentinel):
    pass


class FakeServo(ProductionSentinel):
    pass


class SimulatedSentinel(ProductionSentinel):
    pass


SimulatedSentinel.__module__ = "simulated_test"


def production_provider() -> ProductionAdapterProvider:
    return ProductionAdapterProvider(
        servo=FakeServo,
        audio=FakeSyncPlayer,
        bluetooth=ProductionSentinel,
        esp32=ProductionSentinel,
        smoke=ProductionSentinel,
        gaze=ProductionSentinel,
    )


def test_simulated_startup_selects_one_common_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    adapters = build_adapters(clock=SimulatedClock(), audio_duration_s=300.0)

    assert adapters.mode == "simulated"
    assert isinstance(adapters.servo, SimulatedHardware)
    assert isinstance(adapters.audio, SimulatedAudioPlayer)
    assert isinstance(adapters.bluetooth, SimulatedBluetoothAdapter)
    assert isinstance(adapters.esp32, SimulatedESP32Adapter)
    assert isinstance(adapters.smoke, SimulatedSmokeAdapter)
    assert isinstance(adapters.gaze, SimulatedGazeAdapter)
    assert isinstance(adapters.servo, ServoAdapter)
    assert isinstance(adapters.audio, AudioAdapter)
    assert isinstance(adapters.bluetooth, BluetoothAdapter)
    assert isinstance(adapters.esp32, ESP32Adapter)
    assert isinstance(adapters.smoke, SmokeAdapter)
    assert isinstance(adapters.gaze, GazeAdapter)


def test_phase8_runtime_mode_name_wins_over_legacy_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "production")
    monkeypatch.setenv("SKULL_RUNTIME_MODE", "simulated")

    assert resolve_runtime_mode() == "simulated"

    monkeypatch.delenv("SKULL_RUNTIME_MODE")
    assert resolve_runtime_mode() == "production"


def test_production_startup_requires_explicit_provider_and_never_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    assert resolve_runtime_mode() == "production"
    with pytest.raises(RuntimeConfigurationError, match="explicit provider"):
        build_adapters()

    selected = build_adapters(production=production_provider())
    assert selected.mode == "production"
    assert all(
        not adapter.__class__.__module__.startswith("simulated_")
        for adapter in (
            selected.servo,
            selected.audio,
            selected.bluetooth,
            selected.esp32,
            selected.smoke,
            selected.gaze,
        )
    )


def test_production_provider_returning_simulator_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    provider = ProductionAdapterProvider(
        servo=SimulatedSentinel,
        audio=FakeSyncPlayer,
        bluetooth=ProductionSentinel,
        esp32=ProductionSentinel,
        smoke=ProductionSentinel,
        gaze=ProductionSentinel,
    )
    with pytest.raises(RuntimeConfigurationError, match="simulated adapters"):
        build_adapters(production=provider)


def test_simulation_cannot_be_selected_without_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    with pytest.raises(RuntimeConfigurationError, match="explicit"):
        resolve_runtime_mode("simulated")
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "unexpected")
    with pytest.raises(RuntimeConfigurationError, match="production.*simulated"):
        resolve_runtime_mode()


def test_readiness_exposes_only_the_validated_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    assert runtime_readiness() == {
        "ready": True,
        "mode": "production",
        "simulation": False,
        "selection": "production",
    }
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    assert runtime_readiness() == {
        "ready": True,
        "mode": "simulated",
        "simulation": True,
        "selection": "explicit-simulation",
    }


def test_production_launchers_pin_and_reject_simulated_mode() -> None:
    root = Path(__file__).parents[2]
    service_source = (root / "install_skull.sh").read_text(encoding="utf-8")
    launcher_source = (root / "launch_servo_sync.sh").read_text(encoding="utf-8")
    assert "Environment=SKULL_HARDWARE_MODE=production" in service_source
    assert "SKULL_HARDWARE_MODE=simulated refuse" in service_source
    assert 'SKULL_HARDWARE_MODE:-production' in launcher_source
    assert "SKULL_HARDWARE_MODE=simulated refuse" in launcher_source


def test_health_ready_route_exposes_mode_without_hardware_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sync = types.ModuleType("sync_player")
    def set_on_track_finished(self, callback) -> None:
        self.callback = callback

    fake_sync.SyncPlayer = type(
        "FakePlayer",
        (),
        {
            "__init__": lambda self: None,
            "set_on_track_finished": set_on_track_finished,
            "status": lambda self: {"running": False},
        },
    )
    fake_loop = types.ModuleType("loop_player")
    fake_loop.LoopPlayer = type(
        "FakeLoopPlayer",
        (),
        {"__init__": lambda self, *args, **kwargs: None},
    )
    fake_logger = types.ModuleType("logger")
    class FakeLogger:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    fake_logger.servo_logger = types.SimpleNamespace(
        logger=FakeLogger()
    )
    for name, module in {
        "sync_player": fake_sync,
        "loop_player": fake_loop,
        "logger": fake_logger,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKULL_SMOKE_WEBHOOK_URL", "")
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    sys.modules.pop("web_app", None)
    import web_app

    response = web_app.app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["mode"] == "real"
    assert response.get_json()["checks"]["runtime_initialized"] is False

    web_app.initialize_runtime(
        sync_player_cls=fake_sync.SyncPlayer,
        loop_player_cls=fake_loop.LoopPlayer,
    )
    response = web_app.app.test_client().get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["mode"] == "real"
    web_app.cleanup_runtime()
