"""Dependency-injected playback orchestration for the Skull."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from adapters import AudioAdapter, GazeAdapter, ServoAdapter, SmokeAdapter
from domain.errors import DomainError, OperationNotAllowedError
from domain.models import PlaybackState
from domain.state_machine import PlaybackStateMachine, TransitionResult


class PlaybackService:
    """Coordinate playback without constructing a platform singleton.

    The legacy web façade is not switched to this service until ``SKULL-06.7``.
    This service is nevertheless complete enough to exercise the new boundary
    contract with either real adapters or explicit fakes.
    """

    def __init__(
        self,
        *,
        audio: AudioAdapter,
        servo: ServoAdapter,
        smoke: SmokeAdapter,
        gaze: GazeAdapter,
        on_state: Callable[[TransitionResult], None] | None = None,
        state_machine: PlaybackStateMachine | None = None,
    ) -> None:
        self.audio = audio
        self.servo = servo
        self.smoke = smoke
        self.gaze = gaze
        self.state_machine = state_machine or PlaybackStateMachine(on_transition=on_state)
        self.session_name: str | None = None

    def _safe_outputs(self, reason: str) -> None:
        try:
            self.audio.stop(reason=reason)
        finally:
            self.servo.neutral()

    def _failed(self, exc: BaseException) -> None:
        self._safe_outputs("error")
        try:
            self.state_machine.transition("failed")
        except OperationNotAllowedError:
            pass
        if isinstance(exc, DomainError):
            raise exc
        raise RuntimeError("Playback service failed") from exc

    def start(self, session_dir: str | Path, session_name: str) -> None:
        self.state_machine.transition("start")
        self.session_name = str(session_name)
        try:
            self.audio.load(session_dir)
            self.audio.play()
            self.state_machine.transition("started")
            if self.session_name.casefold() == "accueil":
                try:
                    self.smoke.trigger(self.session_name)
                except DomainError:
                    # Smoke is an optional external effect; audio remains live,
                    # matching the legacy non-fatal webhook behavior.
                    pass
        except Exception as exc:
            self._failed(exc)

    def pause(self) -> None:
        self.state_machine.transition("pause")
        try:
            self.audio.pause()
        except Exception as exc:
            self._failed(exc)

    def resume(self) -> None:
        self.state_machine.transition("resume")
        try:
            self.audio.resume()
        except Exception as exc:
            self._failed(exc)

    def stop(self, reason: str = "stop") -> None:
        self.state_machine.transition("stop")
        try:
            try:
                self.audio.stop(reason=reason)
            finally:
                self.servo.neutral()
        except Exception as exc:
            try:
                self.state_machine.transition("failed")
            except OperationNotAllowedError:
                pass
            if isinstance(exc, DomainError):
                raise exc
            raise RuntimeError("Playback service stop failed") from exc

        if self.state_machine.state is PlaybackState.STOPPING:
            self.state_machine.transition("stopped")
        self.session_name = None

    def cleanup(self) -> None:
        try:
            cleanup = getattr(self.audio, "cleanup", None)
            if callable(cleanup):
                cleanup()
        finally:
            try:
                self.gaze.stop()
            finally:
                self.servo.cleanup()


__all__ = ["PlaybackService"]
