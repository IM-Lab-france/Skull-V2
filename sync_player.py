"""
SyncPlayer: synchronize playback of an mp3 file with servo timeline.

- Uses Timeline (timeline.py) for servo frames.
- Uses rpi_hardware.Hardware to drive 4 servos.
- Plays mp3 via pydub + simpleaudio.
- Provides play/pause/resume/stop API.
- Honors channel enable/disable flags (eye_left, eye_right, neck, jaw).

MODIFIED: Integrates GazeReceiver so skull follows gaze when:
 - during playback: neck/eyes overridden by gaze if fresh
 - when no playback active: background follower applies gaze continuously

Behaviour:
- jaw remains driven by timeline (never overridden by gaze).
- channels flags control whether gaze is allowed to move neck/eyes.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional, Dict, Callable

from pydub import AudioSegment
import simpleaudio as sa

from timeline import Timeline
from rpi_hardware import Hardware
from logger import servo_logger

# nouveau : import du récepteur gaze
from gaze_receiver import GazeReceiver


class SyncPlayer:
    def __init__(self):
        self.hw = Hardware()
        self.timeline: Optional[Timeline] = None
        self.audio: Optional[AudioSegment] = None
        self._play_obj: Optional[sa.PlayObject] = None
        self._thread: Optional[threading.Thread] = None

        self._running = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()

        self.session_dir: Optional[Path] = None

        # timing
        self._start_time: float = 0.0  # reference start (shifted during pause)
        self._pause_pos_ms: int = 0  # audio position at pause

        # channels (default: all enabled) - can be updated by web_app via set_channels()
        self.channels: Dict[str, bool] = {
            "eye_left": True,
            "eye_right": True,
            "neck": True,
            "jaw": True,
        }

        # last targets (for frozen channels we keep last position)
        self._last_target = {
            "jaw": 130.0,
            "neck": 90.0,
            "eye_left": 90.0,
            "eye_right": 90.0,
        }

        # --- Gaze integration ---
        # Démarre le récepteur UDP pour écouter le gaze_server
        self.gaze = GazeReceiver(host="127.0.0.1", port=5005)
        # flag pour activer/désactiver le tracking depuis l'app principale (peut être exposé via web_app)
        self.track_enable = False

        # background thread qui applique la consigne gaze quand aucun morceau n'est en lecture
        self._gaze_thread = threading.Thread(
            target=self._gaze_follower_loop, daemon=True
        )
        self._gaze_thread_running = threading.Event()
        self._gaze_thread_running.set()
        self._gaze_thread.start()

        self._on_track_finished: Optional[Callable[[str, Optional[str], Optional[str]], None]] = None
        self._stop_reason: Optional[str] = None

    # ---------------- File loading ----------------
    def load(self, session_dir: str | Path):
        """
        Charge une session depuis un répertoire.
        Cherche automatiquement les fichiers JSON et MP3 dans le nouveau format.
        """
        d = Path(session_dir)
        self.session_dir = d

        if not d.exists() or not d.is_dir():
            raise FileNotFoundError(f"Répertoire de session introuvable: {d}")

        # Chercher les fichiers JSON et MP3
        json_files = list(d.glob("*.json"))
        mp3_files = list(d.glob("*.mp3"))

        if not json_files:
            raise FileNotFoundError(f"Aucun fichier JSON trouvé dans {d}")
        if not mp3_files:
            raise FileNotFoundError(f"Aucun fichier MP3 trouvé dans {d}")

        # Prendre le premier fichier de chaque type
        json_file = json_files[0]
        mp3_file = mp3_files[0]

        servo_logger.logger.info(f"LOADING_SESSION | Dir: {d.name}")
        servo_logger.logger.info(
            f"LOADING_FILES | JSON: {json_file.name} | MP3: {mp3_file.name}"
        )

        # Charger les fichiers
        try:
            self.timeline = Timeline.from_json(json_file)
            self.audio = AudioSegment.from_mp3(mp3_file)
        except Exception as e:
            servo_logger.logger.error(f"LOADING_ERROR | {e}")
            raise

        # Initialiser la session de logging
        session_name = f"{d.name}_{json_file.stem}"
        audio_duration = len(self.audio) / 1000.0  # durée en secondes
        servo_logger.start_session(session_name, audio_duration)

        servo_logger.logger.info(
            f"SESSION_LOADED | Duration: {audio_duration:.3f}s | Frames: {len(self.timeline.frames)}"
        )

    # ---------------- Channels control ----------------
    def set_channels(self, flags: Dict[str, bool]) -> None:
        with self._lock:
            old_channels = self.channels.copy()
            for k in ("eye_left", "eye_right", "neck", "jaw"):
                if k in flags:
                    self.channels[k] = bool(flags[k])

            # Logger les changements de canaux
            for k in ("eye_left", "eye_right", "neck", "jaw"):
                if old_channels[k] != self.channels[k]:
                    status = "ENABLED" if self.channels[k] else "DISABLED"
                    servo_logger.logger.info(f"CHANNEL_{status} | {k}")

    def set_on_track_finished(self, callback: Optional[Callable[[str, Optional[str], Optional[str]], None]]):
        """Register a callback invoked when playback ends."""
        with self._lock:
            self._on_track_finished = callback

    # ---------------- Gaze follower loop (background) ----------------
    def _gaze_follower_loop(self):
        """
        Boucle de fond qui centre automatiquement la personne détectée dans l'image.
        Au lieu d'appliquer directement les angles gaze, on calcule l'erreur par rapport
        au centre et on ajuste progressivement pour maintenir la personne au centre.
        """
        SLEEP = 0.02

        # Paramètres de contrôle PID simplifié (Proportionnel seulement)
        KP_NECK = (
            0.3  # Gain proportionnel pour le cou (plus élevé = réaction plus rapide)
        )
        KP_EYES = 0.4  # Gain proportionnel pour les yeux

        # Zone morte pour éviter les micro-ajustements
        DEADZONE_NECK = 3.0  # degrés
        DEADZONE_EYES = 2.0  # degrés

        # Limites de vitesse (degrés par seconde)
        MAX_SPEED_NECK = 15.0
        MAX_SPEED_EYES = 60.0

        last_time = time.time()

        while self._gaze_thread_running.is_set():
            try:
                if self._running.is_set():
                    time.sleep(SLEEP)
                    continue

                cmd = self.gaze.get_command()
                if cmd and self.track_enable and cmd.get("mode", "") == "track":
                    current_time = time.time()
                    dt = current_time - last_time
                    last_time = current_time

                    with self._lock:
                        ch = self.channels.copy()

                    try:
                        # Les angles du gaze_server représentent la POSITION de la personne
                        # par rapport au centre. Pour centrer, on doit bouger dans la direction opposée.

                        # neck - centrage horizontal
                        if ch.get("neck", True) and "neck" in cmd:
                            neck_data = cmd["neck"]
                            if "yaw_deg" in neck_data:
                                # L'erreur est l'angle actuel de la personne par rapport au centre
                                error_deg = float(neck_data["yaw_deg"])

                                # Si erreur < deadzone, ne pas bouger
                                if abs(error_deg) > DEADZONE_NECK:
                                    # Commande proportionnelle : bouger dans la direction opposée à l'erreur
                                    correction_deg = -error_deg * KP_NECK

                                    # Limiter la vitesse de correction
                                    max_correction = MAX_SPEED_NECK * dt
                                    correction_deg = max(
                                        -max_correction,
                                        min(max_correction, correction_deg),
                                    )

                                    # Position cible = position actuelle + correction
                                    current_neck = self._last_target.get("neck", 90.0)
                                    target_neck = current_neck + correction_deg

                                    # Limites hardware (selon rpi_hardware.py)
                                    target_neck = max(0.0, min(180.0, target_neck))

                                    self.hw.set_named_angle(
                                        "neck_pan", target_neck, log_enabled=True
                                    )
                                    self._last_target["neck"] = target_neck

                                    servo_logger.logger.debug(
                                        f"CENTERING_NECK | Error: {error_deg:.1f}° | Correction: {correction_deg:.1f}° | Target: {target_neck:.1f}°"
                                    )
                        else:
                            servo_logger.log_servo_command(
                                "neck_pan", self._last_target["neck"], enabled=False
                            )

                        # eyes - centrage horizontal (même logique)
                        if ch.get("eye_left", True) and "eyeL" in cmd:
                            eyeL_data = cmd["eyeL"]
                            if "yaw_deg" in eyeL_data:
                                error_deg = float(eyeL_data["yaw_deg"])

                                if abs(error_deg) > DEADZONE_EYES:
                                    correction_deg = -error_deg * KP_EYES
                                    max_correction = MAX_SPEED_EYES * dt
                                    correction_deg = max(
                                        -max_correction,
                                        min(max_correction, correction_deg),
                                    )

                                    current_eyeL = self._last_target.get(
                                        "eye_left", 90.0
                                    )
                                    target_eyeL = current_eyeL + correction_deg
                                    target_eyeL = max(
                                        60.0, min(120.0, target_eyeL)
                                    )  # Limites yeux

                                    self.hw.set_named_angle(
                                        "eye_left", target_eyeL, log_enabled=True
                                    )
                                    self._last_target["eye_left"] = target_eyeL

                                    servo_logger.logger.debug(
                                        f"CENTERING_EYEL | Error: {error_deg:.1f}° | Target: {target_eyeL:.1f}°"
                                    )
                        else:
                            servo_logger.log_servo_command(
                                "eye_left", self._last_target["eye_left"], enabled=False
                            )

                        if ch.get("eye_right", True) and "eyeR" in cmd:
                            eyeR_data = cmd["eyeR"]
                            if "yaw_deg" in eyeR_data:
                                error_deg = float(eyeR_data["yaw_deg"])

                                if abs(error_deg) > DEADZONE_EYES:
                                    correction_deg = -error_deg * KP_EYES
                                    max_correction = MAX_SPEED_EYES * dt
                                    correction_deg = max(
                                        -max_correction,
                                        min(max_correction, correction_deg),
                                    )

                                    current_eyeR = self._last_target.get(
                                        "eye_right", 90.0
                                    )
                                    target_eyeR = current_eyeR + correction_deg
                                    target_eyeR = max(60.0, min(120.0, target_eyeR))

                                    self.hw.set_named_angle(
                                        "eye_right", target_eyeR, log_enabled=True
                                    )
                                    self._last_target["eye_right"] = target_eyeR

                                    servo_logger.logger.debug(
                                        f"CENTERING_EYER | Error: {error_deg:.1f}° | Target: {target_eyeR:.1f}°"
                                    )
                        else:
                            servo_logger.log_servo_command(
                                "eye_right",
                                self._last_target["eye_right"],
                                enabled=False,
                            )

                    except Exception as e:
                        servo_logger.logger.warning(f"CENTERING_ERROR | {e}")
                        time.sleep(SLEEP)
                        continue
                else:
                    # Pas de commande gaze - retour lent vers neutre
                    last_time = time.time()
                    time.sleep(SLEEP)
                    continue

                time.sleep(SLEEP)
            except Exception as e:
                servo_logger.logger.error(
                    f"[SyncPlayer._gaze_follower_loop] erreur: {e}"
                )
                time.sleep(0.1)

    # ---------------- Runner thread ----------------
    def _runner(self):
        assert self.timeline and self.audio

        finish_reason = "completed"
        error_message: Optional[str] = None
        frame_count = 0
        skipped_frames = 0

        try:
            start_pos_ms = getattr(self, "_resume_from_ms", 0)
            self._stop_reason = None

            if start_pos_ms:
                segment = self.audio[start_pos_ms:]
                self._play_obj = sa.play_buffer(
                    segment.raw_data,
                    num_channels=segment.channels,
                    bytes_per_sample=segment.sample_width,
                    sample_rate=segment.frame_rate,
                )
                servo_logger.logger.info(f"AUDIO_RESUME | From: {start_pos_ms/1000.0:.3f}s")
            else:
                self._play_obj = sa.play_buffer(
                    self.audio.raw_data,
                    num_channels=self.audio.channels,
                    bytes_per_sample=self.audio.sample_width,
                    sample_rate=self.audio.frame_rate,
                )
                servo_logger.logger.info("AUDIO_START | From beginning")

            servo_logger.start_audio()

            now = time.time()
            if start_pos_ms:
                self._start_time = now - (start_pos_ms / 1000.0)
            else:
                self._start_time = now
            self._running.set()
            self._paused.clear()
            if hasattr(self, "_resume_from_ms"):
                delattr(self, "_resume_from_ms")

            for frame in self.timeline:
                frame_count += 1

                while self._paused.is_set() and self._running.is_set():
                    time.sleep(0.01)
                    self._start_time += 0.01
                if not self._running.is_set():
                    finish_reason = self._stop_reason or "stopped"
                    break

                target_time = self._start_time + frame["timestamp_ms"] / 1000.0
                delay = target_time - time.time()

                if delay < -0.05:
                    skipped_frames += 1
                    if skipped_frames % 10 == 1:
                        servo_logger.logger.warning(
                            f"TIMING_LAG | Frame delayed by {-delay:.3f}s | Skipped: {skipped_frames}"
                        )

                if delay > 0:
                    time.sleep(delay)

                tgt = {
                    "jaw": float(frame["jaw_deg"]),
                    "neck": float(frame["neck_pan_deg"]),
                    "eye_left": float(frame["eye_left_deg"]),
                    "eye_right": float(frame["eye_right_deg"]),
                }
                self._last_target.update(tgt)

                with self._lock:
                    ch = self.channels.copy()

                gaze_cmd = None
                if self.track_enable:
                    gaze_cmd = self.gaze.get_command()

                if ch.get("jaw", True):
                    self.hw.set_named_angle("jaw", tgt["jaw"], log_enabled=True)
                else:
                    servo_logger.log_servo_command("jaw", self._last_target["jaw"], enabled=False)

                if gaze_cmd and gaze_cmd.get("mode") == "track" and ch.get("neck", True):
                    try:
                        neck_angle = float(gaze_cmd["neck"]["yaw_deg"])
                        self.hw.set_named_angle("neck_pan", neck_angle, log_enabled=True)
                        self._last_target["neck"] = neck_angle
                    except Exception as e:
                        servo_logger.logger.warning(f"GAZE_OVERRIDE_NECK_ERROR | {e}")
                        if ch.get("neck", True):
                            self.hw.set_named_angle("neck_pan", tgt["neck"], log_enabled=True)
                        else:
                            servo_logger.log_servo_command("neck_pan", self._last_target["neck"], enabled=False)
                else:
                    if ch.get("neck", True):
                        self.hw.set_named_angle("neck_pan", tgt["neck"], log_enabled=True)
                    else:
                        servo_logger.log_servo_command("neck_pan", self._last_target["neck"], enabled=False)

                if gaze_cmd and gaze_cmd.get("mode") == "track" and ch.get("eye_left", True):
                    try:
                        eyeL_angle = float(gaze_cmd["eyeL"]["yaw_deg"])
                        self.hw.set_named_angle("eye_left", eyeL_angle, log_enabled=True)
                        self._last_target["eye_left"] = eyeL_angle
                    except Exception as e:
                        servo_logger.logger.warning(f"GAZE_OVERRIDE_EYEL_ERROR | {e}")
                        if ch.get("eye_left", True):
                            self.hw.set_named_angle("eye_left", tgt["eye_left"], log_enabled=True)
                        else:
                            servo_logger.log_servo_command("eye_left", self._last_target["eye_left"], enabled=False)
                else:
                    if ch.get("eye_left", True):
                        self.hw.set_named_angle("eye_left", tgt["eye_left"], log_enabled=True)
                    else:
                        servo_logger.log_servo_command("eye_left", self._last_target["eye_left"], enabled=False)

                if gaze_cmd and gaze_cmd.get("mode") == "track" and ch.get("eye_right", True):
                    try:
                        eyeR_angle = float(gaze_cmd["eyeR"]["yaw_deg"])
                        self.hw.set_named_angle("eye_right", eyeR_angle, log_enabled=True)
                        self._last_target["eye_right"] = eyeR_angle
                    except Exception as e:
                        servo_logger.logger.warning(f"GAZE_OVERRIDE_EYER_ERROR | {e}")
                        if ch.get("eye_right", True):
                            self.hw.set_named_angle("eye_right", tgt["eye_right"], log_enabled=True)
                        else:
                            servo_logger.log_servo_command("eye_right", self._last_target["eye_right"], enabled=False)
                else:
                    if ch.get("eye_right", True):
                        self.hw.set_named_angle("eye_right", tgt["eye_right"], log_enabled=True)
                    else:
                        servo_logger.log_servo_command("eye_right", self._last_target["eye_right"], enabled=False)

        except Exception as exc:
            finish_reason = "error"
            error_message = str(exc)
            servo_logger.logger.exception(f"PLAYBACK_ERROR | {exc}")
        finally:
            try:
                if self._play_obj:
                    self._play_obj.wait_done()
                    servo_logger.log_audio_end()
            except Exception as wait_exc:
                servo_logger.logger.warning(f"AUDIO_WAIT_ERROR | {wait_exc}")
            finally:
                self._running.clear()

                servo_logger.logger.info(
                    f"PLAYBACK_STATS | Total frames: {frame_count} | Skipped: {skipped_frames}"
                )
                if frame_count > 0:
                    skip_percentage = (skipped_frames / frame_count) * 100
                    if skip_percentage > 5:
                        servo_logger.logger.warning(
                            f"HIGH_SKIP_RATE | {skip_percentage:.1f}% frames skipped"
                        )

                self.hw.neutral()
                servo_logger.end_session()

                with self._lock:
                    stop_reason = self._stop_reason
                    callback = self._on_track_finished
                    self._stop_reason = None

                if finish_reason == "stopped" and stop_reason:
                    finish_reason = stop_reason

                session_name = None
                if self.session_dir:
                    try:
                        session_name = self.session_dir.name
                    except Exception:
                        session_name = str(self.session_dir)

                if callback:
                    try:
                        callback(finish_reason, error_message, session_name)
                    except Exception:
                        servo_logger.logger.exception("PLAYBACK_CALLBACK_ERROR")

                self._play_obj = None

    # ---------------- Public API ----------------
    def play(self):
        if self._thread and self._thread.is_alive():
            self.stop()
        # start fresh
        if hasattr(self, "_resume_from_ms"):
            delattr(self, "_resume_from_ms")
        servo_logger.logger.info("PLAYBACK_START")
        self._thread = threading.Thread(target=self._runner, daemon=True)
        self._thread.start()

    def pause(self):
        if self._running.is_set() and not self._paused.is_set():
            self._paused.set()
            # compute current audio position (timeline elapsed)
            self._pause_pos_ms = int((time.time() - self._start_time) * 1000)
            servo_logger.logger.info(
                f"PLAYBACK_PAUSE | Position: {self._pause_pos_ms/1000.0:.3f}s"
            )
            # stop audio
            if self._play_obj:
                self._play_obj.stop()

    def resume(self):
        if self._paused.is_set():
            # mark resume position and relaunch runner thread from there
            self._paused.clear()
            self._resume_from_ms = int(self._pause_pos_ms)
            servo_logger.logger.info(
                f"PLAYBACK_RESUME | From: {self._resume_from_ms/1000.0:.3f}s"
            )
            # restart worker thread at resume position
            if self._thread and self._thread.is_alive():
                # let current thread exit cleanly
                self._running.clear()
                self._thread.join()
            self._running.set()
            self._thread = threading.Thread(target=self._runner, daemon=True)
            self._thread.start()

    def stop(self, reason: str = "stop"):
        servo_logger.logger.info(f"PLAYBACK_STOP | reason={reason}")
        with self._lock:
            self._stop_reason = reason

        self._running.clear()
        self._paused.clear()

        if self._play_obj:
            try:
                self._play_obj.stop()
            except Exception as e:
                servo_logger.logger.warning(f"AUDIO_STOP_ERROR | {e}")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                servo_logger.logger.warning(
                    "THREAD_STOP_TIMEOUT | Thread did not stop cleanly"
                )
        self.hw.neutral()
        servo_logger.end_session()


    def status(self):
        st = {
            "running": self._running.is_set(),
            "paused": self._paused.is_set(),
            "session": str(self.session_dir) if self.session_dir else None,
            "channels": dict(self.channels),
            "track_enable": bool(self.track_enable),
        }
        if self._running.is_set():
            st["elapsed_ms"] = int((time.time() - self._start_time) * 1000)
        # Diagnostics gaze
        cmd = self.gaze.get_command()
        if cmd:
            st["gaze_last_ts"] = cmd.get("ts")
            st["gaze_mode"] = cmd.get("mode")
            st["gaze_target_id"] = cmd.get("target_id")
        else:
            st["gaze_last_ts"] = None
            st["gaze_mode"] = None
            st["gaze_target_id"] = None
        return st

    # ---------------- Cleanup on object deletion ----------------
    def __del__(self):
        try:
            # stop gaze thread
            self._gaze_thread_running.clear()
            if self._gaze_thread.is_alive():
                self._gaze_thread.join(timeout=0.5)
        except Exception:
            pass
        try:
            self.gaze.stop()
        except Exception:
            pass


__all__ = ["SyncPlayer"]
