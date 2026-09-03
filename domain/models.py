"""Immutable domain values used to describe Skull playback."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Session:
    """A playable Skull session and its optional presentation category."""

    name: str
    category: str | None = None


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """One normalized servo frame, using the legacy output field names."""

    timestamp_ms: int
    jaw_deg: float
    neck_pan_deg: float
    eye_left_deg: float
    eye_right_deg: float

    def as_legacy_dict(self) -> dict[str, object]:
        """Return the dictionary shape consumed by the existing player."""
        return {
            "timestamp_ms": self.timestamp_ms,
            "jaw_deg": self.jaw_deg,
            "neck_pan_deg": self.neck_pan_deg,
            "eye_left_deg": self.eye_left_deg,
            "eye_right_deg": self.eye_right_deg,
        }


@dataclass(frozen=True, slots=True)
class PlaylistItem:
    """One in-memory queued session."""

    id: int
    session: str
    added_at: float
    retries: int = 0

    def as_legacy_dict(self) -> dict[str, object]:
        """Return the queue dictionary shape preserved by the legacy API."""
        return {
            "id": self.id,
            "session": self.session,
            "added_at": self.added_at,
            "retries": self.retries,
        }


class PlaybackState(str, Enum):
    """Stable vocabulary for the playback lifecycle."""

    IDLE = "idle"
    STARTING = "starting"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PlaybackSnapshot:
    """A typed view of the playback status exposed by the legacy façade."""

    state: PlaybackState
    session: str | None = None
    elapsed_ms: int | None = None
    channels: Mapping[str, bool] = field(default_factory=dict)
    track_enable: bool = False

    def as_legacy_dict(self) -> dict[str, object]:
        """Return the pre-refactoring status keys and value types."""
        payload: dict[str, object] = {
            "running": self.state in {
                PlaybackState.STARTING,
                PlaybackState.PLAYING,
                PlaybackState.PAUSED,
                PlaybackState.STOPPING,
            },
            "paused": self.state is PlaybackState.PAUSED,
            "session": self.session,
            "channels": dict(self.channels),
            "track_enable": self.track_enable,
        }
        if self.elapsed_ms is not None:
            payload["elapsed_ms"] = self.elapsed_ms
        return payload


__all__ = [
    "PlaybackSnapshot",
    "PlaybackState",
    "PlaylistItem",
    "Session",
    "TimelineEvent",
]
