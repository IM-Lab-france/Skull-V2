"""Local-only tests for the explicit SKULL-04.2 servo simulator."""

from __future__ import annotations

import importlib
import sys

import pytest

from adapters import ServoAdapter
from simulated_hardware import SimulatedHardware


def test_simulation_requires_explicit_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    with pytest.raises(RuntimeError, match="SKULL_HARDWARE_MODE=simulated"):
        SimulatedHardware()

    monkeypatch.setenv("SKULL_HARDWARE_MODE", "production")
    with pytest.raises(RuntimeError, match="SKULL_HARDWARE_MODE=simulated"):
        SimulatedHardware()


def test_simulator_import_has_no_raspberry_dependency() -> None:
    forbidden = {"board", "busio", "adafruit_pca9685"}
    assert "simulated_hardware" in sys.modules
    assert not any(
        name in sys.modules
        or any(name.startswith(f"{prefix}.") for prefix in forbidden)
        for name in forbidden
    )
    assert importlib.import_module("simulated_hardware").__name__ == (
        "simulated_hardware"
    )


def test_trace_matches_reference_clamps_and_pulses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    hardware = SimulatedHardware(timestamp_step=0.5)
    assert isinstance(hardware, ServoAdapter)

    hardware.set_named_angle("jaw", 200)
    hardware.set_named_angle("eye_left", 30)
    hardware.set_named_angle("eye_right", 90)
    hardware.set_named_angle("neck_pan", -10)

    assert [(entry.channel, entry.name) for entry in hardware.trace] == [
        (0, "jaw"),
        (1, "eye_left"),
        (2, "eye_right"),
        (3, "neck_pan"),
    ]
    assert [entry.requested_deg for entry in hardware.trace] == [200.0, 30.0, 90.0, -10.0]
    assert [entry.clamped_deg for entry in hardware.trace] == [185.0, 60.0, 90.0, 0.0]
    assert [entry.pulse_us for entry in hardware.trace] == pytest.approx(
        [2555.5555555556, 1166.6666666667, 1500.0, 500.0]
    )
    assert [entry.timestamp for entry in hardware.trace] == [0.0, 0.5, 1.0, 1.5]
    assert hardware.ctrl.set_pulse_calls == [
        (entry.channel, pytest.approx(entry.pulse_us)) for entry in hardware.trace
    ]


def test_neutral_offsets_and_cleanup_are_in_memory_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    hardware = SimulatedHardware()
    hardware.set_pitch_offset("eye_left", 0)
    hardware.neutral()

    assert [entry.name for entry in hardware.trace] == [
        "jaw",
        "eye_left",
        "eye_right",
        "neck_pan",
    ]
    assert hardware.trace[1].pulse_us == pytest.approx(1500.0)

    hardware.cleanup()
    assert hardware.ctrl.off_called is True
    assert hardware.ctrl.deinit_called is True
    assert hardware.ctrl.pulses == {}
