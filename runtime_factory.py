"""Explicit runtime adapter selection for the Skull.

This module is intentionally independent from Flask and does not instantiate
hardware at import time.  Simulation requires the explicit environment value
``SKULL_HARDWARE_MODE=simulated``.  Production requires a caller-supplied
provider of real adapters; no simulated fallback is ever attempted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, TypeAlias

from adapters import (
    AudioAdapter,
    BluetoothAdapter,
    ESP32Adapter,
    GazeAdapter,
    ServoAdapter,
    SmokeAdapter,
)


PRODUCTION_MODE = "production"
SIMULATED_MODE = "simulated"
RuntimeMode: TypeAlias = str
AdapterBuilder: TypeAlias = Callable[[], object]


class RuntimeConfigurationError(ValueError):
    """Raised when the selected runtime is unsafe or incomplete."""


@dataclass(frozen=True)
class RuntimeAdapters:
    """The common adapter shape consumed by either runtime mode."""

    mode: RuntimeMode
    servo: ServoAdapter
    audio: AudioAdapter
    bluetooth: BluetoothAdapter
    esp32: ESP32Adapter
    smoke: SmokeAdapter
    gaze: GazeAdapter


@dataclass(frozen=True)
class ProductionAdapterProvider:
    """Explicit constructors for the real production boundaries."""

    servo: AdapterBuilder
    audio: AdapterBuilder
    bluetooth: AdapterBuilder
    esp32: AdapterBuilder
    smoke: AdapterBuilder
    gaze: AdapterBuilder

    def build(self) -> RuntimeAdapters:
        adapters = RuntimeAdapters(
            mode=PRODUCTION_MODE,
            servo=self.servo(),  # type: ignore[arg-type]
            audio=self.audio(),  # type: ignore[arg-type]
            bluetooth=self.bluetooth(),  # type: ignore[arg-type]
            esp32=self.esp32(),  # type: ignore[arg-type]
            smoke=self.smoke(),  # type: ignore[arg-type]
            gaze=self.gaze(),  # type: ignore[arg-type]
        )
        _validate_adapters(adapters)
        simulated = [
            adapter
            for adapter in (
                adapters.servo,
                adapters.audio,
                adapters.bluetooth,
                adapters.esp32,
                adapters.smoke,
                adapters.gaze,
            )
            if adapter.__class__.__module__.startswith("simulated_")
        ]
        if simulated:
            raise RuntimeConfigurationError(
                "production provider returned simulated adapters: "
                + ", ".join(type(adapter).__name__ for adapter in simulated)
            )
        return adapters


def _validate_adapters(adapters: RuntimeAdapters) -> None:
    """Fail startup when a provider does not implement the common ports."""
    expected = (
        ("servo", adapters.servo, ServoAdapter),
        ("audio", adapters.audio, AudioAdapter),
        ("bluetooth", adapters.bluetooth, BluetoothAdapter),
        ("esp32", adapters.esp32, ESP32Adapter),
        ("smoke", adapters.smoke, SmokeAdapter),
        ("gaze", adapters.gaze, GazeAdapter),
    )
    for name, adapter, protocol in expected:
        if not isinstance(adapter, protocol):
            raise RuntimeConfigurationError(
                f"{name} adapter does not implement {protocol.__name__}"
            )


def resolve_runtime_mode(mode: str | None = None) -> RuntimeMode:
    """Resolve and validate the mode without constructing any adapter.

    Omitting the variable preserves the legacy production default.  Selecting
    simulation is stricter: the environment must explicitly contain the same
    value, so a caller cannot silently turn a production process into a test
    process through a default or an unrelated argument.
    """
    configured = os.environ.get("SKULL_HARDWARE_MODE")
    candidate = (mode if mode is not None else configured or PRODUCTION_MODE).strip().lower()
    if candidate not in {PRODUCTION_MODE, SIMULATED_MODE}:
        raise RuntimeConfigurationError(
            "SKULL_HARDWARE_MODE must be 'production' or 'simulated'"
        )
    if candidate == SIMULATED_MODE and configured != SIMULATED_MODE:
        raise RuntimeConfigurationError(
            "simulation requires explicit SKULL_HARDWARE_MODE=simulated"
        )
    if mode == PRODUCTION_MODE and configured == SIMULATED_MODE:
        raise RuntimeConfigurationError(
            "requested production conflicts with SKULL_HARDWARE_MODE=simulated"
        )
    return candidate


def build_adapters(
    mode: str | None = None,
    *,
    production: ProductionAdapterProvider | None = None,
    audio_duration_s: float = 300.0,
    clock=None,
) -> RuntimeAdapters:
    """Build one common adapter bundle with an explicit mode boundary."""
    selected = resolve_runtime_mode(mode)
    if selected == PRODUCTION_MODE:
        if production is None:
            raise RuntimeConfigurationError(
                "production requires an explicit provider of real adapters"
            )
        return production.build()

    from simulated_audio import SimulatedAudioPlayer
    from simulated_external import (
        SimulatedBluetoothAdapter,
        SimulatedESP32Adapter,
        SimulatedSmokeAdapter,
    )
    from simulated_gaze import SimulatedGazeAdapter
    from simulated_hardware import SimulatedHardware

    adapters = RuntimeAdapters(
        mode=SIMULATED_MODE,
        servo=SimulatedHardware(),
        audio=SimulatedAudioPlayer(duration_s=audio_duration_s, clock=clock),
        bluetooth=SimulatedBluetoothAdapter(clock=clock),
        esp32=SimulatedESP32Adapter(clock=clock),
        smoke=SimulatedSmokeAdapter(clock=clock),
        gaze=SimulatedGazeAdapter(),
    )
    _validate_adapters(adapters)
    return adapters


def runtime_readiness(mode: str | None = None) -> dict[str, object]:
    """Return a secret-free configuration readiness snapshot for HTTP health."""
    try:
        selected = resolve_runtime_mode(mode)
    except RuntimeConfigurationError as exc:
        return {
            "ready": False,
            "mode": None,
            "error": str(exc),
        }
    return {
        "ready": True,
        "mode": selected,
        "simulation": selected == SIMULATED_MODE,
        "selection": "explicit-simulation" if selected == SIMULATED_MODE else "production",
    }


__all__ = [
    "PRODUCTION_MODE",
    "SIMULATED_MODE",
    "ProductionAdapterProvider",
    "RuntimeAdapters",
    "RuntimeConfigurationError",
    "build_adapters",
    "resolve_runtime_mode",
    "runtime_readiness",
]
