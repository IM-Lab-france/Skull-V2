"""Deterministic in-memory audio player for local Skull simulations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters import AudioAdapter, TrackFinishedCallback
from simulation_clock import Clock, SimulatedClock


class SimulatedAudioPlayer:
    """Small ``AudioAdapter`` implementation with no audio device access.

    The duration is supplied by the test or simulation harness.  Playback
    advances only when the injected clock advances and the player is observed
    through ``status``/``tick`` or the convenience method ``advance``.
    Therefore a five-minute session can be completed without five minutes of
    wall-clock waiting.
    """

    def __init__(
        self,
        duration_s: float,
        clock: Clock | None = None,
    ) -> None:
        duration_s = float(duration_s)
        if duration_s < 0:
            raise ValueError("duration_s must be non-negative")
        self.duration_s = duration_s
        self.clock = clock or SimulatedClock()
        self.session_dir: Path | None = None
        self._session_name: str | None = None
        self._position_s = 0.0
        self._state = "stopped"
        self._stop_reason: str | None = None
        self._last_clock_s = self.clock.monotonic()
        self._on_track_finished: TrackFinishedCallback | None = None
        self.calls: list[tuple[Any, ...]] = []

    def _sync_position(self) -> None:
        now = self.clock.monotonic()
        if self._state != "playing":
            self._last_clock_s = now
            return

        elapsed = max(0.0, now - self._last_clock_s)
        self._last_clock_s = now
        self._position_s = min(self.duration_s, self._position_s + elapsed)
        if self._position_s < self.duration_s:
            return

        self._state = "completed"
        callback = self._on_track_finished
        if callback is not None:
            callback("completed", None, self._session_name)

    def load(self, session_dir: str | Path) -> None:
        """Load a named synthetic session without reading the filesystem."""
        self.session_dir = Path(session_dir)
        self._session_name = self.session_dir.name or str(self.session_dir)
        self._position_s = 0.0
        self._state = "stopped"
        self._stop_reason = None
        self._last_clock_s = self.clock.monotonic()
        self.calls.append(("load", str(session_dir)))

    def play(self) -> None:
        """Start from the beginning, matching the main player's play API."""
        self._sync_position()
        self._position_s = 0.0
        self._stop_reason = None
        self._state = "playing"
        self._last_clock_s = self.clock.monotonic()
        self.calls.append(("play",))
        self._sync_position()

    def pause(self) -> None:
        """Freeze the current position without advancing logical time."""
        self._sync_position()
        if self._state == "playing":
            self._state = "paused"
        self.calls.append(("pause",))

    def resume(self) -> None:
        """Continue from the paused position."""
        self._sync_position()
        if self._state == "paused":
            self._state = "playing"
            self._last_clock_s = self.clock.monotonic()
        self.calls.append(("resume",))

    def stop(self, reason: str = "stop") -> None:
        """Stop playback and preserve the observed position for diagnostics."""
        self._sync_position()
        self._state = "stopped"
        self._stop_reason = reason
        self.calls.append(("stop", reason))

    def set_on_track_finished(
        self, callback: TrackFinishedCallback | None
    ) -> None:
        self._on_track_finished = callback
        self.calls.append(("set_on_track_finished", callback))

    def tick(self) -> None:
        """Observe the player and apply elapsed logical time."""
        self._sync_position()
        self.calls.append(("tick",))

    def advance(self, seconds: float) -> None:
        """Advance a simulated clock and observe the resulting player state."""
        advance = getattr(self.clock, "advance", None)
        if not callable(advance):
            raise TypeError("advance requires a clock exposing advance(seconds)")
        advance(seconds)
        self.tick()

    def status(self) -> dict[str, object]:
        """Return a JSON-compatible snapshot of the synthetic playback state."""
        self._sync_position()
        return {
            "state": self._state,
            "running": self._state == "playing",
            "paused": self._state == "paused",
            "completed": self._state == "completed",
            "position_s": round(self._position_s, 6),
            "duration_s": self.duration_s,
            "session": str(self.session_dir) if self.session_dir else None,
            "stop_reason": self._stop_reason,
            "simulated": True,
        }


# Short alias for callers that use the task's noun rather than the adapter's
# concrete name.
SimulatedAudio = SimulatedAudioPlayer


__all__ = ["SimulatedAudio", "SimulatedAudioPlayer"]
