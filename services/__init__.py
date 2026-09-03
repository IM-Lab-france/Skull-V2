"""Application services assembled from explicit Skull adapters."""

from .playback import PlaybackService
from .legacy_playback import LegacyPlaybackService

__all__ = ["LegacyPlaybackService", "PlaybackService"]
