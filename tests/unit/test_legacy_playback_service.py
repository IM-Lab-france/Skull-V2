from __future__ import annotations

from pathlib import Path

import pytest

from services import LegacyPlaybackService
from tests.fixtures.fake_adapters import FakeAudioAdapter


class FakeLoop:
    def __init__(self, *, fail_suppress: bool = False) -> None:
        self.fail_suppress = fail_suppress
        self.calls: list[tuple[str, float | None]] = []

    def suppress_for_session(self) -> None:
        self.calls.append(("suppress", None))
        if self.fail_suppress:
            raise RuntimeError("synthetic suppression failure")

    def release_suppression(self, delay: float = 0.0) -> None:
        self.calls.append(("release", delay))


def test_legacy_service_preserves_order_and_injects_runtime_components() -> None:
    audio = FakeAudioAdapter()
    loop = FakeLoop()
    service = LegacyPlaybackService(audio=audio, loop=loop)

    service.start(Path("synthetic"))
    service.pause()
    service.resume()
    service.stop("skip")

    assert [call[0] for call in audio.calls] == [
        "load",
        "play",
        "pause",
        "resume",
        "stop",
    ]
    assert loop.calls == [("suppress", None)]
    assert audio.calls[-1] == ("stop", "skip")


def test_legacy_service_releases_loop_when_audio_start_fails() -> None:
    class BrokenAudio(FakeAudioAdapter):
        def play(self) -> None:
            raise OSError("synthetic audio failure")

    loop = FakeLoop()
    with pytest.raises(OSError):
        LegacyPlaybackService(audio=BrokenAudio(), loop=loop).start(Path("synthetic"))
    assert loop.calls == [("suppress", None), ("release", 0.0)]


def test_legacy_service_continues_when_loop_suppression_fails() -> None:
    audio = FakeAudioAdapter()
    loop = FakeLoop(fail_suppress=True)
    LegacyPlaybackService(audio=audio, loop=loop).start(Path("synthetic"))
    assert ("play",) in audio.calls
