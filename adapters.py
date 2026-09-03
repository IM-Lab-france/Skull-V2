"""Interfaces for the Skull's external hardware boundaries.

This module deliberately contains only standard-library typing constructs.  It
must remain importable on a Windows development machine where Raspberry Pi
libraries, audio devices, Bluetooth services, and GPIO/I2C buses are absent.

The protocols describe the smallest surface currently consumed by the core.
They do not contain policy, retries, clamping, routing, or business rules;
those responsibilities stay in the core or in a concrete adapter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable, Protocol, TypeAlias, runtime_checkable


JsonObject: TypeAlias = Mapping[str, Any]
BluetoothDevice: TypeAlias = Mapping[str, str]
BluetoothStatus: TypeAlias = Mapping[str, Any]
TrackFinishedCallback: TypeAlias = Callable[[str, str | None, str | None], None]


@runtime_checkable
class ServoAdapter(Protocol):
    """Command the four named servos through the PCA9685 boundary.

    ``ValueError``/``KeyError`` represent an unknown servo or invalid angle;
    ``OSError`` and ``RuntimeError`` represent a hardware or bus failure.
    The adapter must not silently replace a real hardware failure with a
    simulated command.
    """

    def set_named_angle(
        self, name: str, deg: float, log_enabled: bool = True
    ) -> None: ...

    def neutral(self) -> None: ...

    def cleanup(self) -> None: ...

    def set_pitch_offset(self, servo_name: str, offset: float) -> None: ...


@runtime_checkable
class AudioAdapter(Protocol):
    """Load and control one Skull session's main audio track.

    ``load`` may raise ``FileNotFoundError`` or ``ValueError`` for invalid
    session data.  ``play``, ``pause``, ``resume`` and ``stop`` may raise
    ``OSError`` or ``RuntimeError`` when the audio backend is unavailable.
    ``status`` returns a JSON-compatible mapping owned by the adapter.
    """

    def load(self, session_dir: str | Path) -> None: ...

    def play(self) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self, reason: str = "stop") -> None: ...

    def status(self) -> JsonObject: ...

    def set_on_track_finished(
        self, callback: TrackFinishedCallback | None
    ) -> None: ...


@runtime_checkable
class BluetoothAdapter(Protocol):
    """Expose the distinct Bluetooth operations used by the legacy UI.

    ``scan`` returns discovered devices, ``pair`` performs the pairing/trust/
    connection workflow, ``connect`` only reconnects an already known device,
    and ``info`` reads its state.  Operations may raise ``TimeoutError``,
    ``ConnectionError`` or ``OSError``; callers decide how to expose failures.
    """

    def scan(self) -> Sequence[BluetoothDevice]: ...

    def pair(self, address: str) -> BluetoothStatus: ...

    def connect(self, address: str) -> bool: ...

    def info(self, address: str) -> BluetoothStatus | None: ...


@runtime_checkable
class ESP32Adapter(Protocol):
    """Send one JSON request to the ESP32 boundary.

    ``path`` is a relative API path.  ``method`` is the HTTP method and
    ``json_payload`` is absent for requests without a body.  Implementations
    may raise ``TimeoutError``, ``ConnectionError``, ``OSError`` or a concrete
    adapter communication exception for HTTP/JSON failures.
    """

    def request(
        self,
        path: str,
        method: str = "GET",
        json_payload: JsonObject | None = None,
    ) -> JsonObject: ...


@runtime_checkable
class SmokeAdapter(Protocol):
    """Trigger the smoke effect without embedding webhook policy."""

    def trigger(self, session_name: str) -> None: ...


@runtime_checkable
class GazeAdapter(Protocol):
    """Read the latest fresh gaze command and stop its receiver."""

    def get_command(self) -> JsonObject | None: ...

    def stop(self, timeout: float = 1.0) -> None: ...


__all__ = [
    "AudioAdapter",
    "BluetoothAdapter",
    "BluetoothDevice",
    "BluetoothStatus",
    "ESP32Adapter",
    "GazeAdapter",
    "JsonObject",
    "ServoAdapter",
    "SmokeAdapter",
    "TrackFinishedCallback",
]
