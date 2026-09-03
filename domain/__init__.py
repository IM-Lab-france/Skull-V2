"""Pure domain vocabulary for Skull.

This package deliberately contains no web, operating-system, network, audio,
or Raspberry Pi dependency.  Boundary modules may translate these values to
the legacy dictionaries and HTTP responses still used by the application.
"""

from .errors import (
    ConflictError,
    DependencyUnavailableError,
    DomainError,
    InvalidInputError,
    NotFoundError,
    OperationNotAllowedError,
)
from .models import (
    PlaybackSnapshot,
    PlaybackState,
    PlaylistItem,
    Session,
    TimelineEvent,
)
from .session_catalog import SessionCatalog, SessionInspection
from .playlist import PlaybackStateStore, PlaylistStore, RandomSessionSelector
from .state_machine import (
    PlaybackEffect,
    PlaybackEvent,
    PlaybackStateMachine,
    TRANSITIONS,
    Transition,
    TransitionNotAllowedError,
    TransitionResult,
)

__all__ = [
    "ConflictError",
    "DependencyUnavailableError",
    "DomainError",
    "InvalidInputError",
    "NotFoundError",
    "OperationNotAllowedError",
    "PlaybackSnapshot",
    "PlaybackState",
    "PlaybackStateStore",
    "PlaylistItem",
    "PlaylistStore",
    "RandomSessionSelector",
    "PlaybackEffect",
    "PlaybackEvent",
    "PlaybackStateMachine",
    "Session",
    "SessionCatalog",
    "SessionInspection",
    "TimelineEvent",
    "TRANSITIONS",
    "Transition",
    "TransitionNotAllowedError",
    "TransitionResult",
]
