"""Explicit, deterministic servo hardware simulation for local tests.

The module intentionally has no Raspberry, I2C, GPIO, audio, or Bluetooth
imports.  Construction is refused unless ``SKULL_HARDWARE_MODE=simulated`` is
set explicitly; there is no fallback from the real driver to this module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict


SIMULATED_MODE = "simulated"


@dataclass
class SimulatedServoSpec:
    """Mechanical reference values copied from the real driver."""

    channel: int
    min_us: int = 500
    max_us: int = 2500
    min_deg: float = 0.0
    max_deg: float = 180.0
    pitch_offset: float = 0.0

    def clamp(self, deg: float) -> float:
        return max(self.min_deg, min(self.max_deg, deg))

    def angle_to_us(self, deg: float) -> float:
        effective_deg = self.clamp(deg + self.pitch_offset)
        span = self.max_us - self.min_us
        return self.min_us + (effective_deg / 180.0) * span


@dataclass(frozen=True)
class ServoCommand:
    """One logical servo command captured by the simulator."""

    channel: int
    name: str
    requested_deg: float
    clamped_deg: float
    pulse_us: float
    timestamp: float


class SimulatedPCA9685Controller:
    """In-memory equivalent of the real PCA9685 controller surface."""

    def __init__(self, address: int = 0x40, frequency: int = 50) -> None:
        if frequency <= 0:
            raise ValueError("frequency must be positive")
        self.address = address
        self.frequency = frequency
        self.period_us = 1_000_000.0 / frequency
        self.pulses: dict[int, float] = {}
        self.set_pulse_calls: list[tuple[int, float]] = []
        self.off_called = False
        self.deinit_called = False

    def set_pulse_us(self, channel: int, pulse_us: float) -> None:
        """Store the same period-clamped pulse accepted by the real driver."""
        if not 0 <= channel < 16:
            raise ValueError(f"invalid PCA9685 channel: {channel}")
        clamped_pulse = max(0.0, min(self.period_us, float(pulse_us)))
        self.pulses[channel] = clamped_pulse
        self.set_pulse_calls.append((channel, clamped_pulse))

    def off(self) -> None:
        """Record the equivalent of disabling all PCA9685 channels."""
        self.pulses.clear()
        self.off_called = True

    def deinit(self) -> None:
        """Disable outputs and mark the simulated bus as released."""
        self.off()
        self.deinit_called = True


class SimulatedHardware:
    """Hardware-compatible facade that records servo commands in memory.

    The ``SPECS`` values deliberately match ``rpi_hardware.Hardware.SPECS``.
    ``timestamp`` starts at zero and advances by ``timestamp_step`` for each
    named servo command, making traces deterministic and independent of wall
    clock scheduling.  Construction raises ``RuntimeError`` unless the caller
    explicitly selects the simulation mode through the environment.
    """

    SPECS: Dict[str, SimulatedServoSpec] = {
        "jaw": SimulatedServoSpec(channel=0, min_deg=110, max_deg=185),
        "eye_left": SimulatedServoSpec(
            channel=1, min_deg=60, max_deg=120, pitch_offset=-14
        ),
        "eye_right": SimulatedServoSpec(channel=2, min_deg=60, max_deg=120),
        "neck_pan": SimulatedServoSpec(channel=3, min_deg=0, max_deg=180),
    }

    def __init__(
        self,
        address: int = 0x40,
        frequency: int = 50,
        timestamp_step: float = 1.0,
    ) -> None:
        mode = os.environ.get("SKULL_HARDWARE_MODE")
        if mode != SIMULATED_MODE:
            raise RuntimeError(
                "SimulatedHardware requires explicit "
                "SKULL_HARDWARE_MODE=simulated"
            )
        if timestamp_step <= 0:
            raise ValueError("timestamp_step must be positive")

        self.ctrl = SimulatedPCA9685Controller(address=address, frequency=frequency)
        self.SPECS = {
            name: SimulatedServoSpec(
                channel=spec.channel,
                min_us=spec.min_us,
                max_us=spec.max_us,
                min_deg=spec.min_deg,
                max_deg=spec.max_deg,
                pitch_offset=spec.pitch_offset,
            )
            for name, spec in type(self).SPECS.items()
        }
        self.timestamp_step = float(timestamp_step)
        self._logical_time = 0.0
        self.trace: list[ServoCommand] = []
        # Alias kept convenient for callers that describe the result as a log.
        self.commands = self.trace

    def _next_timestamp(self) -> float:
        timestamp = self._logical_time
        self._logical_time += self.timestamp_step
        return timestamp

    def set_named_angle(self, name: str, deg: float, log_enabled: bool = True) -> None:
        """Clamp, convert, and capture one named servo command without I2C."""
        del log_enabled  # Kept for compatibility with the real facade.
        spec = self.SPECS[name]
        requested_deg = float(deg)
        clamped_deg = spec.clamp(requested_deg)
        pulse_us = spec.angle_to_us(clamped_deg)
        self.ctrl.set_pulse_us(spec.channel, pulse_us)
        self.trace.append(
            ServoCommand(
                channel=spec.channel,
                name=name,
                requested_deg=requested_deg,
                clamped_deg=clamped_deg,
                pulse_us=pulse_us,
                timestamp=self._next_timestamp(),
            )
        )

    def neutral(self) -> None:
        """Capture the same safe-neutral sequence as the real facade."""
        self.set_named_angle("jaw", 180, log_enabled=True)
        self.set_named_angle("eye_left", 90, log_enabled=True)
        self.set_named_angle("eye_right", 90, log_enabled=True)
        self.set_named_angle("neck_pan", 90, log_enabled=True)

    def cleanup(self) -> None:
        """Release the simulated controller without touching a system device."""
        self.ctrl.deinit()

    def set_pitch_offset(self, servo_name: str, offset: float) -> None:
        """Apply the same per-servo offset mutation as the real facade."""
        if servo_name in self.SPECS:
            self.SPECS[servo_name].pitch_offset = float(offset)


__all__ = [
    "SIMULATED_MODE",
    "ServoCommand",
    "SimulatedHardware",
    "SimulatedPCA9685Controller",
    "SimulatedServoSpec",
]
