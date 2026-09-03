"""Explicit, thread-safe playback lifecycle for Skull.

The state machine owns lifecycle policy only.  It does not import Flask,
audio, GPIO, Bluetooth, or Raspberry Pi libraries.  Boundary code executes
the declared effects; this keeps the legacy HTTP façade and the hardware
adapters separate from the domain decision.

Transition table
----------------

| Current   | Event             | Next      | Effects                          |
|-----------|-------------------|-----------|----------------------------------|
| IDLE      | start             | STARTING  | start audio/timeline, publish    |
| IDLE      | stop              | IDLE      | safe stop, publish               |
| STARTING  | started           | PLAYING   | publish                          |
| STARTING  | stop              | STOPPING  | stop audio/timeline/smoke        |
| STARTING  | failed            | ERROR     | safe stop, publish error         |
| PLAYING   | pause             | PAUSED    | pause audio/timeline, publish    |
| PLAYING   | stop              | STOPPING  | stop audio/timeline/smoke        |
| PLAYING   | completed         | IDLE      | stop timeline/smoke, publish     |
| PLAYING   | failed            | ERROR     | safe stop, publish error         |
| PAUSED    | resume            | PLAYING   | resume audio/timeline, publish   |
| PAUSED    | stop              | STOPPING  | stop audio/timeline/smoke        |
| PAUSED    | failed            | ERROR     | safe stop, publish error         |
| STOPPING  | stopped           | IDLE      | safe stop, publish               |
| STOPPING  | stop              | STOPPING  | safe stop (idempotent)            |
| STOPPING  | failed            | ERROR     | safe stop, publish error         |
| ERROR     | reset             | IDLE      | safe stop, publish               |
| ERROR     | stop              | IDLE      | safe stop, publish               |

Any event not listed above raises :class:`TransitionNotAllowedError` and
leaves the state unchanged.  ``stop`` is deliberately idempotent from IDLE,
STOPPING, and ERROR so repeated shutdown requests cannot restart playback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Callable, Mapping

from .errors import OperationNotAllowedError
from .models import PlaybackState


class TransitionNotAllowedError(OperationNotAllowedError):
    """The requested lifecycle event is invalid for the current state."""

    def __init__(self, state: PlaybackState, event: str) -> None:
        self.state = state
        self.event = event
        super().__init__(f"Transition interdite: {state.name} + {event}")


class PlaybackEvent(str, Enum):
    """Events accepted by :class:`PlaybackStateMachine`."""

    START = "start"
    STARTED = "started"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    RESET = "reset"


class PlaybackEffect(str, Enum):
    """Effects declared for an adapter boundary to execute."""

    AUDIO_START = "audio_start"
    AUDIO_PAUSE = "audio_pause"
    AUDIO_RESUME = "audio_resume"
    AUDIO_STOP = "audio_stop"
    TIMELINE_START = "timeline_start"
    TIMELINE_PAUSE = "timeline_pause"
    TIMELINE_RESUME = "timeline_resume"
    TIMELINE_STOP = "timeline_stop"
    SMOKE_START = "smoke_start"
    SMOKE_STOP = "smoke_stop"
    SAFE_OUTPUTS = "safe_outputs"
    PUBLISH_STATE = "publish_state"


@dataclass(frozen=True, slots=True)
class Transition:
    """One allowed state transition and its declared effects."""

    source: PlaybackState
    event: PlaybackEvent
    target: PlaybackState
    effects: tuple[PlaybackEffect, ...]


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Atomic result returned after a lifecycle event is accepted."""

    transition: Transition
    sequence: int

    @property
    def state(self) -> PlaybackState:
        return self.transition.target

    @property
    def effects(self) -> tuple[PlaybackEffect, ...]:
        return self.transition.effects


_PUBLISH = (PlaybackEffect.PUBLISH_STATE,)
_SAFE = (
    PlaybackEffect.AUDIO_STOP,
    PlaybackEffect.TIMELINE_STOP,
    PlaybackEffect.SMOKE_STOP,
    PlaybackEffect.SAFE_OUTPUTS,
    PlaybackEffect.PUBLISH_STATE,
)
_STOP = (
    PlaybackEffect.AUDIO_STOP,
    PlaybackEffect.TIMELINE_STOP,
    PlaybackEffect.SMOKE_STOP,
    PlaybackEffect.PUBLISH_STATE,
)


def _transition(
    source: PlaybackState,
    event: PlaybackEvent,
    target: PlaybackState,
    effects: tuple[PlaybackEffect, ...],
) -> Transition:
    return Transition(source, event, target, effects)


TRANSITIONS: Mapping[PlaybackState, Mapping[PlaybackEvent, Transition]] = {
    PlaybackState.IDLE: {
        PlaybackEvent.START: _transition(
            PlaybackState.IDLE,
            PlaybackEvent.START,
            PlaybackState.STARTING,
            (
                PlaybackEffect.AUDIO_START,
                PlaybackEffect.TIMELINE_START,
                PlaybackEffect.SMOKE_START,
                *_PUBLISH,
            ),
        ),
        PlaybackEvent.STOP: _transition(
            PlaybackState.IDLE, PlaybackEvent.STOP, PlaybackState.IDLE, _SAFE
        ),
    },
    PlaybackState.STARTING: {
        PlaybackEvent.STARTED: _transition(
            PlaybackState.STARTING,
            PlaybackEvent.STARTED,
            PlaybackState.PLAYING,
            _PUBLISH,
        ),
        PlaybackEvent.STOP: _transition(
            PlaybackState.STARTING,
            PlaybackEvent.STOP,
            PlaybackState.STOPPING,
            _STOP,
        ),
        PlaybackEvent.FAILED: _transition(
            PlaybackState.STARTING,
            PlaybackEvent.FAILED,
            PlaybackState.ERROR,
            _SAFE,
        ),
    },
    PlaybackState.PLAYING: {
        PlaybackEvent.PAUSE: _transition(
            PlaybackState.PLAYING,
            PlaybackEvent.PAUSE,
            PlaybackState.PAUSED,
            (
                PlaybackEffect.AUDIO_PAUSE,
                PlaybackEffect.TIMELINE_PAUSE,
                *_PUBLISH,
            ),
        ),
        PlaybackEvent.STOP: _transition(
            PlaybackState.PLAYING,
            PlaybackEvent.STOP,
            PlaybackState.STOPPING,
            _STOP,
        ),
        PlaybackEvent.COMPLETED: _transition(
            PlaybackState.PLAYING,
            PlaybackEvent.COMPLETED,
            PlaybackState.IDLE,
            (
                PlaybackEffect.TIMELINE_STOP,
                PlaybackEffect.SMOKE_STOP,
                *_PUBLISH,
            ),
        ),
        PlaybackEvent.FAILED: _transition(
            PlaybackState.PLAYING,
            PlaybackEvent.FAILED,
            PlaybackState.ERROR,
            _SAFE,
        ),
    },
    PlaybackState.PAUSED: {
        PlaybackEvent.RESUME: _transition(
            PlaybackState.PAUSED,
            PlaybackEvent.RESUME,
            PlaybackState.PLAYING,
            (
                PlaybackEffect.AUDIO_RESUME,
                PlaybackEffect.TIMELINE_RESUME,
                *_PUBLISH,
            ),
        ),
        PlaybackEvent.STOP: _transition(
            PlaybackState.PAUSED,
            PlaybackEvent.STOP,
            PlaybackState.STOPPING,
            _STOP,
        ),
        PlaybackEvent.FAILED: _transition(
            PlaybackState.PAUSED,
            PlaybackEvent.FAILED,
            PlaybackState.ERROR,
            _SAFE,
        ),
    },
    PlaybackState.STOPPING: {
        PlaybackEvent.STOPPED: _transition(
            PlaybackState.STOPPING,
            PlaybackEvent.STOPPED,
            PlaybackState.IDLE,
            _SAFE,
        ),
        PlaybackEvent.STOP: _transition(
            PlaybackState.STOPPING,
            PlaybackEvent.STOP,
            PlaybackState.STOPPING,
            _SAFE,
        ),
        PlaybackEvent.FAILED: _transition(
            PlaybackState.STOPPING,
            PlaybackEvent.FAILED,
            PlaybackState.ERROR,
            _SAFE,
        ),
    },
    PlaybackState.ERROR: {
        PlaybackEvent.RESET: _transition(
            PlaybackState.ERROR,
            PlaybackEvent.RESET,
            PlaybackState.IDLE,
            _SAFE,
        ),
        PlaybackEvent.STOP: _transition(
            PlaybackState.ERROR,
            PlaybackEvent.STOP,
            PlaybackState.IDLE,
            _SAFE,
        ),
    },
}


class PlaybackStateMachine:
    """Serialize lifecycle events and return their adapter effects."""

    def __init__(
        self,
        initial_state: PlaybackState = PlaybackState.IDLE,
        on_transition: Callable[[TransitionResult], None] | None = None,
    ) -> None:
        if initial_state not in TRANSITIONS:
            raise ValueError(f"État initial inconnu: {initial_state}")
        self._state = initial_state
        self._sequence = 0
        self._lock = threading.RLock()
        self._on_transition = on_transition

    @property
    def state(self) -> PlaybackState:
        with self._lock:
            return self._state

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence

    def transition(self, event: PlaybackEvent | str) -> TransitionResult:
        """Apply one event atomically, or raise without changing state."""
        try:
            normalized = event if isinstance(event, PlaybackEvent) else PlaybackEvent(event)
        except ValueError:
            with self._lock:
                raise TransitionNotAllowedError(self._state, str(event)) from None

        with self._lock:
            transition = TRANSITIONS[self._state].get(normalized)
            if transition is None:
                raise TransitionNotAllowedError(self._state, normalized.value)
            self._state = transition.target
            self._sequence += 1
            result = TransitionResult(transition, self._sequence)
            callback = self._on_transition

        if callback is not None:
            callback(result)
        return result


__all__ = [
    "PlaybackEffect",
    "PlaybackEvent",
    "PlaybackStateMachine",
    "TRANSITIONS",
    "Transition",
    "TransitionNotAllowedError",
    "TransitionResult",
]
