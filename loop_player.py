"""
Background loop audio player with fade in/out control.

This helper streams an AudioSegment in short chunks via simpleaudio so that
volume envelopes can be applied on demand (used when a main track starts).
"""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any, Optional

import simpleaudio as sa
from pydub import AudioSegment

from logger import servo_logger


class LoopPlayer:
    """Lightweight audio looper with fade support."""

    def __init__(
        self,
        storage_dir: Path,
        fade_ms: int = 1200,
        chunk_ms: int = 180,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.fade_ms = max(0, int(fade_ms))
        self.chunk_ms = max(60, int(chunk_ms))

        self._lock = threading.RLock()
        self._audio: Optional[AudioSegment] = None
        self._audio_path: Optional[Path] = None
        self._display_name: Optional[str] = None
        self._position_ms: int = 0

        self._user_enabled: bool = False
        self._suppression_count: int = 0

        self._volume: float = 0.0
        self._fade: Optional[dict[str, float]] = None

        self._stop_event = threading.Event()
        self._control_event = threading.Event()
        self._thread = threading.Thread(target=self._runner, daemon=True)
        self._thread.start()

        self._resume_timer: Optional[threading.Timer] = None
        self._resume_deadline: Optional[float] = None

    # ----------------------- Public API -----------------------
    def replace_audio(self, mp3_path: Path, display_name: Optional[str] = None) -> None:
        """Load a new MP3 loop and reset playback."""
        audio = AudioSegment.from_file(mp3_path)
        if len(audio) == 0:
            raise ValueError("Fichier audio vide")

        with self._lock:
            self._audio = audio
            self._audio_path = Path(mp3_path)
            self._display_name = display_name or Path(mp3_path).name
            self._position_ms = 0
            self._volume = 0.0
            self._fade = None
        servo_logger.logger.info(
            "LOOP_AUDIO_LOADED | file=%s | duration=%.3fs",
            mp3_path.name,
            len(audio) / 1000.0,
        )
        self._notify()

    def set_enabled(self, enabled: bool, fade_ms: Optional[int] = None) -> bool:
        """Enable or disable loop playback."""
        with self._lock:
            if self._user_enabled == enabled:
                return False
            self._user_enabled = enabled
            if not enabled:
                self._ensure_fade_locked(0.0, fade_ms)
        servo_logger.logger.info("LOOP_ENABLED=%s", enabled)
        self._notify()
        return True

    def suppress_for_session(self, fade_ms: Optional[int] = None) -> None:
        """Temporarily fade out loop while a main track plays."""
        with self._lock:
            self._cancel_resume_timer_locked()
            self._suppression_count += 1
            self._ensure_fade_locked(0.0, fade_ms)
        servo_logger.logger.debug(
            "LOOP_SUPPRESS | count=%s", self._suppression_count
        )
        self._notify()

    def release_suppression(self, delay: float = 5.0) -> None:
        """Schedule loop resume once the main track has finished."""

        def _release() -> None:
            with self._lock:
                self._resume_timer = None
                self._resume_deadline = None
                if self._suppression_count > 0:
                    self._suppression_count -= 1
            servo_logger.logger.debug(
                "LOOP_SUPPRESSION_RELEASED | count=%s", self._suppression_count
            )
            self._notify()

        with self._lock:
            if self._suppression_count == 0:
                return
            self._cancel_resume_timer_locked()
            if delay <= 0:
                _release()
                return
            self._resume_deadline = time.time() + delay
            timer = threading.Timer(delay, _release)
            timer.daemon = True
            self._resume_timer = timer
            timer.start()
            servo_logger.logger.debug(
                "LOOP_SUPPRESSION_TIMER | delay=%.2fs | count=%s",
                delay,
                self._suppression_count,
            )

    def cancel_all_suppression(self) -> None:
        """Immediate resume (used if playback failed)."""
        with self._lock:
            self._cancel_resume_timer_locked()
            self._suppression_count = 0
        self._notify()

    def status(self) -> dict[str, Any]:
        """Expose current loop state for the API."""
        with self._lock:
            suppressed = self._suppression_count > 0
            resume_in = None
            if suppressed and self._resume_deadline:
                resume_in = max(0.0, self._resume_deadline - time.time())
            playing = (
                self._audio is not None
                and self._user_enabled
                and not suppressed
                and self._volume > 0.01
            )
            return {
                "enabled": self._user_enabled,
                "suppressed": suppressed,
                "playing": playing,
                "has_audio": self._audio is not None,
                "filename": self._display_name
                if self._display_name
                else (self._audio_path.name if self._audio_path else None),
                "volume": round(self._volume, 3),
                "fade_active": self._fade is not None,
                "resuming_in": resume_in,
            }

    def stop(self) -> None:
        """Terminate the runner thread (used during shutdown)."""
        self._stop_event.set()
        self._notify()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    # ----------------------- Internal helpers -----------------------
    def _notify(self) -> None:
        self._control_event.set()

    def _cancel_resume_timer_locked(self) -> None:
        timer = self._resume_timer
        if timer:
            timer.cancel()
            self._resume_timer = None
        self._resume_deadline = None

    def _ensure_fade_locked(
        self, target_volume: float, fade_ms: Optional[int] = None
    ) -> None:
        target = max(0.0, min(1.0, float(target_volume)))
        fade_duration = self.fade_ms if fade_ms is None else max(0, int(fade_ms))

        self._update_fade_locked()
        if fade_duration == 0:
            self._volume = target
            self._fade = None
            return

        if self._fade:
            current_target = self._fade.get("target", target)
            if abs(current_target - target) < 0.01:
                return

        self._fade = {
            "start": self._volume,
            "target": target,
            "duration": float(fade_duration),
            "start_time": time.monotonic(),
        }

    def _update_fade_locked(self) -> None:
        if not self._fade:
            return
        duration = self._fade["duration"]
        if duration <= 0:
            self._volume = self._fade["target"]
            self._fade = None
            return
        elapsed = (time.monotonic() - self._fade["start_time"]) * 1000.0
        progress = max(0.0, min(1.0, elapsed / duration))
        start = self._fade["start"]
        target = self._fade["target"]
        self._volume = start + (target - start) * progress
        if progress >= 1.0:
            self._fade = None

    def _should_play_locked(self) -> bool:
        return (
            self._audio is not None
            and self._user_enabled
            and self._suppression_count == 0
        )

    def _runner(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                audio = self._audio
                should_play = self._should_play_locked()
                self._update_fade_locked()
                volume = self._volume
                chunk_ms = min(self.chunk_ms, len(audio) if audio else self.chunk_ms)
                pos_ms = self._position_ms if audio else 0

                if should_play and volume < 0.99:
                    self._ensure_fade_locked(1.0)
                elif not should_play and volume > 0.0:
                    self._ensure_fade_locked(0.0)

                self._update_fade_locked()
                volume = self._volume

            if not audio:
                self._control_event.wait(timeout=0.5)
                self._control_event.clear()
                continue

            if volume <= 0.002:
                # Silent phase while waiting for fade or enable.
                time.sleep(0.1)
                continue

            chunk = self._slice_chunk(audio, pos_ms, chunk_ms)
            gain = 0.0
            if volume < 0.999:
                gain = 20.0 * math.log10(max(volume, 0.002))
                chunk = chunk.apply_gain(gain)

            try:
                play_obj = sa.play_buffer(
                    chunk.raw_data,
                    num_channels=chunk.channels,
                    bytes_per_sample=chunk.sample_width,
                    sample_rate=chunk.frame_rate,
                )
                play_obj.wait_done()
            except Exception:
                servo_logger.logger.exception("LOOP_AUDIO_PLAY_ERROR")
                time.sleep(0.5)

            chunk_len = len(chunk)
            if chunk_len <= 0:
                chunk_len = chunk_ms

            with self._lock:
                if self._audio is audio and len(audio) > 0:
                    self._position_ms = (pos_ms + chunk_len) % len(audio)
                else:
                    self._position_ms = 0
                self._update_fade_locked()
                self._volume = self._volume

            # Allow control updates to break latency between chunks.
            self._control_event.wait(timeout=0.001)
            self._control_event.clear()

    def _slice_chunk(
        self, audio: AudioSegment, start_ms: int, length_ms: int
    ) -> AudioSegment:
        total = len(audio)
        if total == 0:
            return AudioSegment.silent(duration=length_ms)

        remaining = max(1, int(length_ms))
        pos = start_ms % total
        pieces: list[AudioSegment] = []

        while remaining > 0:
            end_pos = min(pos + remaining, total)
            if end_pos > pos:
                pieces.append(audio[pos:end_pos])
                remaining -= end_pos - pos
            if end_pos >= total:
                pos = 0
            else:
                pos = end_pos

        if not pieces:
            return AudioSegment.silent(duration=length_ms)

        chunk = pieces[0]
        for piece in pieces[1:]:
            chunk += piece
        return chunk


__all__ = ["LoopPlayer"]
