"""Compatibility service used by the legacy HTTP façade."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class LoopController(Protocol):
    def suppress_for_session(self) -> None: ...

    def release_suppression(self, delay: float = 0.0) -> None: ...


class LegacyPlaybackService:
    """Translate legacy playback calls to explicitly injected components.

    The service intentionally does not change response payloads or own global
    state. A façade creates it with the current runtime components for each
    operation, which keeps ownership explicit while preserving compatibility.
    """

    def __init__(self, *, audio: Any, loop: LoopController) -> None:
        self.audio = audio
        self.loop = loop

    def start(self, session_dir: str | Path) -> None:
        self.audio.load(session_dir)
        suppressed = False
        try:
            self.loop.suppress_for_session()
            suppressed = True
        except Exception:
            # The legacy façade logs this condition and continues playback.
            pass

        try:
            self.audio.play()
        except Exception:
            if suppressed:
                try:
                    self.loop.release_suppression(delay=0.0)
                except Exception:
                    pass
            raise

    def pause(self) -> None:
        self.audio.pause()

    def resume(self) -> None:
        self.audio.resume()

    def stop(self, reason: str = "stop") -> None:
        self.audio.stop(reason=reason)


__all__ = ["LegacyPlaybackService"]
