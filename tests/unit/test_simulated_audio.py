"""Deterministic tests for the SKULL-04.3 clock and audio simulator."""

from __future__ import annotations

from time import perf_counter

import pytest

from adapters import AudioAdapter
from simulated_audio import SimulatedAudioPlayer
from simulation_clock import Clock, SimulatedClock


def test_simulated_clock_advances_without_waiting() -> None:
    clock = SimulatedClock()
    started = perf_counter()
    clock.sleep(300.0)
    elapsed = perf_counter() - started

    assert clock.monotonic() == 300.0
    assert clock.sleep_calls == [300.0]
    assert elapsed < 1.0
    assert isinstance(clock, Clock)


def test_audio_adapter_is_conformant_and_transitions_are_deterministic() -> None:
    clock = SimulatedClock()
    audio = SimulatedAudioPlayer(duration_s=10.0, clock=clock)
    assert isinstance(audio, AudioAdapter)
    audio.load("sessions/demo")
    audio.play()

    audio.advance(2.0)
    assert audio.status()["state"] == "playing"
    assert audio.status()["position_s"] == 2.0

    audio.pause()
    audio.advance(5.0)
    assert audio.status()["state"] == "paused"
    assert audio.status()["position_s"] == 2.0

    audio.resume()
    audio.advance(3.0)
    assert audio.status()["position_s"] == 5.0

    audio.stop("manual")
    audio.advance(5.0)
    assert audio.status()["state"] == "stopped"
    assert audio.status()["position_s"] == 5.0


def test_end_of_track_is_reported_once_without_real_wait() -> None:
    clock = SimulatedClock()
    audio = SimulatedAudioPlayer(duration_s=5.0, clock=clock)
    finished: list[tuple[str, str | None, str | None]] = []
    audio.load("sessions/accueil")
    audio.set_on_track_finished(lambda *args: finished.append(args))
    audio.play()

    audio.advance(4.9)
    assert audio.status()["completed"] is False
    audio.advance(0.1)
    assert audio.status()["state"] == "completed"
    assert finished == [("completed", None, "accueil")]

    audio.advance(10.0)
    assert finished == [("completed", None, "accueil")]


def test_timeline_audio_drift_is_reproducible() -> None:
    clock = SimulatedClock()
    audio = SimulatedAudioPlayer(duration_s=300.0, clock=clock)
    audio.play()

    clock.advance(1.25)
    audio.tick()
    timeline_position_s = 1.0
    audio_position_s = float(audio.status()["position_s"])
    drift_s = audio_position_s - timeline_position_s

    assert audio_position_s == pytest.approx(1.25)
    assert drift_s == pytest.approx(0.25)


def test_invalid_duration_and_real_clock_sleep_are_rejected_or_never_used() -> None:
    with pytest.raises(ValueError, match="duration_s"):
        SimulatedAudioPlayer(duration_s=-1.0)

    clock = SimulatedClock()
    with pytest.raises(ValueError, match="non-negative"):
        clock.sleep(-0.1)
    assert clock.monotonic() == 0.0
