from __future__ import annotations

from pathlib import Path

import pytest

from domain.errors import DependencyUnavailableError
from domain.models import PlaybackState
from services import PlaybackService
from tests.fixtures.fake_adapters import (
    FakeAudioAdapter,
    FakeGazeAdapter,
    FakeServoAdapter,
    FakeSmokeAdapter,
)


def make_service(*, audio=None, smoke=None) -> PlaybackService:
    return PlaybackService(
        audio=audio or FakeAudioAdapter(),
        servo=FakeServoAdapter(),
        smoke=smoke or FakeSmokeAdapter(),
        gaze=FakeGazeAdapter(),
    )


def test_playback_service_uses_only_injected_adapters() -> None:
    audio = FakeAudioAdapter()
    smoke = FakeSmokeAdapter()
    service = make_service(audio=audio, smoke=smoke)

    service.start(Path("synthetic"), "Accueil")
    service.pause()
    service.resume()
    service.stop("test")

    assert service.state_machine.state is PlaybackState.IDLE
    assert audio.calls[:6] == [
        ("load", "synthetic"),
        ("play",),
        ("pause",),
        ("resume",),
        ("stop", "test"),
    ]
    assert smoke.calls == [("trigger", "Accueil")]


def test_smoke_failure_does_not_cancel_audio_playback() -> None:
    class BrokenSmoke(FakeSmokeAdapter):
        def trigger(self, session_name: str) -> None:
            raise DependencyUnavailableError("smoke unavailable")

    audio = FakeAudioAdapter()
    service = make_service(audio=audio, smoke=BrokenSmoke())
    service.start(Path("synthetic"), "Accueil")

    assert service.state_machine.state is PlaybackState.PLAYING
    assert ("play",) in audio.calls
    assert not any(call[0] == "stop" for call in audio.calls)


def test_start_failure_stops_audio_neutralizes_servo_and_enters_error() -> None:
    class BrokenAudio(FakeAudioAdapter):
        def play(self) -> None:
            raise OSError("synthetic audio failure")

    audio = BrokenAudio()
    service = make_service(audio=audio)
    with pytest.raises(RuntimeError, match="Playback service failed"):
        service.start(Path("synthetic"), "Demo")

    assert service.state_machine.state is PlaybackState.ERROR
    assert ("stop", "error") in audio.calls
    assert service.servo.calls[-1] == ("neutral",)


def test_cleanup_calls_injected_owners_only() -> None:
    audio = FakeAudioAdapter()
    gaze = FakeGazeAdapter()
    servo = FakeServoAdapter()
    service = PlaybackService(
        audio=audio,
        servo=servo,
        smoke=FakeSmokeAdapter(),
        gaze=gaze,
    )
    service.cleanup()
    assert gaze.calls == [("stop", 1.0)]
    assert servo.calls == [("cleanup",)]
