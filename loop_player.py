"""
Background loop audio player with fade in/out control (gapless, callback-based).

This implementation streams audio via a PortAudio callback (sounddevice) so that
volume envelopes are applied sample-accurately without restarting the playback.

Modifications:
- The loop source is a fixed WAV file at /opt/skull/data/boucle.wav (exclusive).
- No MP3/upload logic.
- `replace_audio(...)` kept for backward compatibility; it ignores args and
  simply reloads the fixed WAV source.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from logger import servo_logger

# Fixed loop file (WAV) used exclusively.
LOOP_WAV_PATH = Path("/opt/skull/data/boucle.wav")


class LoopPlayer:
    """Lightweight gapless audio looper with fade support using a fixed WAV source."""

    def __init__(
        self,
        storage_dir: Path,
        fade_ms: int = 1200,
        chunk_ms: int = 180,  # kept for backward compatibility; unused
        device: Optional[int] = None,
        blocksize: int = 1024,
        latency: str = "low",
    ) -> None:
        # storage_dir is kept for compatibility; no longer used to locate the loop file
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.fade_ms = max(0, int(fade_ms))
        self.device = device
        self.blocksize = int(blocksize)
        self.latency = latency

        # Playback/loop state (protected by _lock)
        self._lock = threading.RLock()
        self._loop: Optional[np.ndarray] = None  # float32, shape (N, C)
        self._sr: Optional[int] = None
        self._channels: Optional[int] = None
        self._n: int = 0  # samples
        self._pos: int = 0  # current sample index (0..N-1)

        self._user_enabled: bool = False
        self._suppression_count: int = 0

        # Volume/fade state
        self._vol: float = 0.0  # current volume [0..1]
        self._vol_target: float = 0.0  # target volume [0..1]
        self._fade_samples_left: int = 0
        self._fade_step: float = 0.0

        # Control / timers
        self._resume_timer: Optional[threading.Timer] = None
        self._resume_deadline: Optional[float] = None

        # Stream
        self._stream: Optional[sd.OutputStream] = None
        self._stop_flag = False

        # Load the fixed WAV loop at startup and open the stream
        try:
            self._load_fixed_loop()
            self._open_stream()
            servo_logger.logger.info(
                "LOOP_INIT_OK | file=%s | sr=%s | channels=%s | duration=%.3fs",
                LOOP_WAV_PATH.name,
                self._sr,
                self._channels,
                (self._n / float(self._sr)),
            )
        except Exception:
            servo_logger.logger.exception("LOOP_AUDIO_INIT_LOAD_FAILED")

    # ----------------------- Public API -----------------------
    def reload_loop(self) -> None:
        """
        Explicitly reload the fixed WAV loop from disk.
        Useful if the file content is replaced while the process is running.
        """
        with self._lock:
            self._load_fixed_loop()
        servo_logger.logger.info("LOOP_AUDIO_RELOADED | file=%s", LOOP_WAV_PATH.name)

    def replace_audio(self, *_args, **_kwargs) -> None:
        """
        Backward-compatible entry point that used to accept an MP3 path.
        It now *ignores* any provided arguments and reloads the fixed WAV source.
        """
        servo_logger.logger.info(
            "LOOP_REPLACE_AUDIO_CALLED | ignoring args and reloading fixed WAV: %s",
            LOOP_WAV_PATH,
        )
        self.reload_loop()

    def set_enabled(self, enabled: bool, fade_ms: Optional[int] = None) -> bool:
        """Enable or disable loop playback with fade."""
        with self._lock:
            if self._user_enabled == enabled:
                return False
            self._user_enabled = enabled
            if not enabled:
                self._set_fade(target=0.0, fade_ms=fade_ms)
        servo_logger.logger.info("LOOP_ENABLED=%s", enabled)
        return True

    def suppress_for_session(self, fade_ms: Optional[int] = None) -> None:
        """Temporarily fade out loop while a main track plays."""
        with self._lock:
            self._cancel_resume_timer_locked()
            self._suppression_count += 1
            self._set_fade(target=0.0, fade_ms=fade_ms)
        servo_logger.logger.debug("LOOP_SUPPRESS | count=%s", self._suppression_count)

    def release_suppression(self, delay: float = 5.0) -> None:
        """Schedule loop resume once the main track has finished."""

        def _release() -> None:
            with self._lock:
                self._resume_timer = None
                self._resume_deadline = None
                if self._suppression_count > 0:
                    self._suppression_count -= 1

        with self._lock:
            if self._suppression_count == 0:
                return
            self._cancel_resume_timer_locked()
            if delay <= 0:
                _release()
                servo_logger.logger.debug(
                    "LOOP_SUPPRESSION_RELEASED_IMMEDIATE | count=%s",
                    self._suppression_count,
                )
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

    def status(self) -> dict[str, Any]:
        """Expose current loop state for the API."""
        with self._lock:
            suppressed = self._suppression_count > 0
            resume_in = None
            if suppressed and self._resume_deadline:
                resume_in = max(0.0, self._resume_deadline - time.time())
            playing = (
                self._loop is not None
                and self._user_enabled
                and not suppressed
                and self._vol > 0.01
            )
            filename = LOOP_WAV_PATH.name if LOOP_WAV_PATH else None
            return {
                "enabled": self._user_enabled,
                "suppressed": suppressed,
                "playing": playing,
                "has_audio": self._loop is not None,
                "filename": filename,
                "volume": round(self._vol, 3),
                "fade_active": self._fade_samples_left > 0,
                "resuming_in": resume_in,
                "samplerate": self._sr,
                "channels": self._channels,
            }

    def stop(self) -> None:
        """Terminate the audio stream (used during shutdown)."""
        self._stop_flag = True
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None
        with self._lock:
            self._cancel_resume_timer_locked()
        servo_logger.logger.info("LOOP_STOPPED")

    # ----------------------- Internal helpers -----------------------
    def _cancel_resume_timer_locked(self) -> None:
        timer = self._resume_timer
        if timer:
            timer.cancel()
            self._resume_timer = None
        self._resume_deadline = None

    def _set_fade(self, target: float, fade_ms: Optional[int]) -> None:
        target = float(np.clip(target, 0.0, 1.0))
        fade_ms = self.fade_ms if fade_ms is None else max(0, int(fade_ms))
        if self._sr is None or self._sr <= 0:
            # Not initialized; just set directly
            self._vol = target
            self._vol_target = target
            self._fade_samples_left = 0
            self._fade_step = 0.0
            return

        if fade_ms == 0:
            self._vol = target
            self._vol_target = target
            self._fade_samples_left = 0
            self._fade_step = 0.0
            return

        self._vol_target = target
        samples = int(self._sr * (fade_ms / 1000.0))
        if samples <= 0:
            self._vol = target
            self._fade_samples_left = 0
            self._fade_step = 0.0
        else:
            self._fade_samples_left = samples
            self._fade_step = (self._vol_target - self._vol) / samples

    def _should_play_locked(self) -> bool:
        return (
            self._loop is not None
            and self._user_enabled
            and self._suppression_count == 0
        )

    def _update_fade_target_if_needed_locked(self) -> None:
        target = 1.0 if self._should_play_locked() else 0.0
        # Only reprogram a fade if the target meaningfully changes
        if abs(self._vol_target - target) > 1e-6:
            self._set_fade(target=target, fade_ms=self.fade_ms)

    def _load_fixed_loop(self) -> None:
        """Load the fixed WAV loop from LOOP_WAV_PATH. Raises on missing/empty."""
        if not LOOP_WAV_PATH.exists():
            raise FileNotFoundError(f"Loop file not found: {LOOP_WAV_PATH}")

        # Read as float32, always 2D (shape: (N, C))
        data, sr = sf.read(LOOP_WAV_PATH, dtype="float32", always_2d=True)
        if data.size == 0 or data.shape[0] == 0:
            raise ValueError("Fichier audio vide: boucle.wav")

        # Swap atomically
        self._loop = data  # (N, C), float32
        self._sr = int(sr)
        self._channels = int(data.shape[1])
        self._n = int(data.shape[0])
        self._pos = 0
        # Reset fades to silent until enabled
        self._vol = 0.0
        self._vol_target = 0.0
        self._fade_samples_left = 0
        self._fade_step = 0.0

        servo_logger.logger.info(
            "LOOP_AUDIO_LOADED | file=%s | sr=%d | ch=%d | samples=%d | duration=%.3fs",
            LOOP_WAV_PATH.name,
            self._sr,
            self._channels,
            self._n,
            self._n / float(self._sr),
        )

    def _open_stream(self) -> None:
        """Open and start the PortAudio stream."""
        if self._loop is None or self._sr is None or self._channels is None:
            raise RuntimeError("Loop not loaded; cannot open stream.")

        # Close existing if any
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                servo_logger.logger.exception("LOOP_STREAM_REOPEN_ERROR")
            finally:
                self._stream = None

        self._stream = sd.OutputStream(
            samplerate=self._sr,
            channels=self._channels,
            dtype="float32",
            blocksize=self.blocksize,
            device=self.device,
            latency=self.latency,
            dither_off=True,
            callback=self._callback,
        )
        self._stream.start()
        servo_logger.logger.info(
            "LOOP_STREAM_STARTED | blocksize=%d | latency=%s",
            self.blocksize,
            self.latency,
        )

    # ----------------------- Audio callback -----------------------
    def _callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        # Called from PortAudio's realtime thread. Keep this minimal and lock only briefly.
        if status:
            # You can log XRuns etc. (avoid heavy logging here though)
            pass

        loop = self._loop
        if loop is None or self._n == 0 or self._channels is None:
            outdata.fill(0.0)
            return

        with self._lock:
            # Update fade target based on current state
            self._update_fade_target_if_needed_locked()

            n = self._n
            pos = self._pos  # local copy
            vol = self._vol
            vol_target = self._vol_target
            fade_left = self._fade_samples_left
            fade_step = self._fade_step

        # Prepare output (avoid allocations in hot path: outdata is provided)
        # We'll fill outdata in segments, handling wrap-around without concatenation.
        frames_remaining = frames
        write_index = 0

        while frames_remaining > 0:
            to_end = n - pos
            take = to_end if to_end < frames_remaining else frames_remaining
            seg = loop[pos : pos + take]  # view

            # Apply fade/volume
            if fade_left > 0:
                steps = take if take < fade_left else fade_left
                # ramp for 'steps'
                # note: create ramp with np.arange; lightweight for small blocks
                ramp = vol + fade_step * np.arange(steps, dtype=np.float32)
                # clamp
                np.clip(ramp, 0.0, 1.0, out=ramp)
                # first 'steps' samples: apply ramp
                outdata[write_index : write_index + steps, :] = (
                    seg[:steps] * ramp[:, None]
                )
                vol = float(ramp[-1])
                fade_left -= steps
                # tail if any: constant at vol_target
                if take > steps:
                    outdata[write_index + steps : write_index + take, :] = (
                        seg[steps:take] * vol_target
                    )
                    vol = float(vol_target)
                    fade_left = 0
                # else: fully consumed by ramp
            else:
                # Constant volume
                outdata[write_index : write_index + take, :] = seg * vol

            # Advance pointers
            write_index += take
            frames_remaining -= take
            pos = (pos + take) % n

        # Commit updated state back under lock
        with self._lock:
            self._pos = pos
            self._vol = vol
            self._vol_target = vol_target
            self._fade_samples_left = fade_left
            self._fade_step = fade_step

    # ----------------------- Dunder -----------------------
    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass


__all__ = ["LoopPlayer"]
