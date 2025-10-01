"""
Web interface (Flask) to control servo+audio playback sessions + channel toggles.

Features:
- Upload JSON+MP3 into ./data/<scene_name>/ avec nommage personnalisé.
- List available sessions.
- Play / Pause / Resume / Stop endpoints.
- Status endpoint.
- /channels GET/POST to enable/disable eye_left, eye_right, neck, jaw.
- Favicon 204 (no 404 noise).
- Endpoints /logs pour consultation temps réel des logs servo.

MODIFIÉ: Support du nom de scène personnalisé pour les uploads.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import shlex
import subprocess
import tempfile
import time
import traceback
import threading
from itertools import count
from pathlib import Path
from flask import (
    Flask,
    request,
    render_template,
    send_from_directory,
    jsonify,
    Response,
)

from typing import Any, Optional

from sync_player import SyncPlayer
from logger import servo_logger

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(exist_ok=True)
PITCH_CONFIG_PATH = CONFIG_DIR / "pitch_offsets.json"
CHANNELS_CONFIG_PATH = CONFIG_DIR / "channels_state.json"


app = Flask(__name__, static_folder="static", template_folder="templates")
player = SyncPlayer()

VOLUME_TIMEOUT = float(os.environ.get("PLAYLIST_VOLUME_TIMEOUT", "5"))
VOLUME_STEP = int(os.environ.get("PLAYLIST_VOLUME_STEP", "8"))
VOLUME_MAX = int(os.environ.get("PLAYLIST_VOLUME_MAX", "127"))
VOLUME_TOOL = os.environ.get("PLAYLIST_VOLUME_CLI", "bluetoothctl")
_VOLUME_CMD_BASE = shlex.split(VOLUME_TOOL) if VOLUME_TOOL else ["bluetoothctl"]
if not _VOLUME_CMD_BASE:
    _VOLUME_CMD_BASE = ["bluetoothctl"]

VOLUME_ACTIONS = {"up", "down", "mute"}

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

_TRANSPORT_RE = re.compile(r"^Transport\s+(/[^\s]+)", re.MULTILINE)
_VOLUME_RE = re.compile(r"\s*Volume:\s*(?:0x[0-9A-Fa-f]+\s*)?(?:\((\d+)\)|(\d+))")


def _clean_bt_output(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", "\n")
    text = _ANSI_RE.sub("", text)
    return text


def _bluetoothctl_script(*lines: str) -> subprocess.CompletedProcess:
    script_lines = [line for line in lines if line]
    needs_back = script_lines and script_lines[0].startswith("menu ")
    effective_lines = list(script_lines)
    if needs_back:
        effective_lines.append("back")
    effective_lines.append("quit")
    script = "\n".join(effective_lines) + "\n"
    joined = "; ".join(effective_lines)
    proc = subprocess.run(
        _VOLUME_CMD_BASE,
        input=script,
        check=False,
        capture_output=True,
        text=True,
        timeout=VOLUME_TIMEOUT,
    )
    proc.stdout = _clean_bt_output(proc.stdout)
    proc.stderr = _clean_bt_output(proc.stderr)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    logger = servo_logger.logger
    if proc.returncode != 0:
        logger.warning("BTCTL_SCRIPT | cmd=%s | code=%s", joined, proc.returncode)
        if stdout:
            logger.warning("BTCTL_STDOUT | %s", stdout)
        if stderr:
            logger.warning("BTCTL_STDERR | %s", stderr)
    else:
        logger.debug("BTCTL_SCRIPT | cmd=%s | code=%s", joined, proc.returncode)
        if stdout:
            logger.debug("BTCTL_STDOUT | %s", stdout)
        if stderr:
            logger.debug("BTCTL_STDERR | %s", stderr)
    return proc


def _parse_volume_text(text: str) -> int | None:
    if not text:
        return None
    match = _VOLUME_RE.search(text)
    if not match:
        return None
    for group in match.groups():
        if group:
            try:
                return int(group)
            except ValueError:
                continue
    return None


def _pick_transport_path() -> tuple[str | None, subprocess.CompletedProcess]:
    proc = _bluetoothctl_script("menu transport", "list")
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = _TRANSPORT_RE.search(text)
    return (match.group(1) if match else None, proc)


def _get_transport_volume(
    path: str,
) -> tuple[int | None, list[subprocess.CompletedProcess]]:
    history: list[subprocess.CompletedProcess] = []
    proc = _bluetoothctl_script(f"menu transport", f"show {path}")
    history.append(proc)
    volume = _parse_volume_text(proc.stdout)
    if volume is None:
        volume = _parse_volume_text(proc.stderr)
    if volume is None:
        proc = _bluetoothctl_script(f"menu transport", f"volume {path}")
        history.append(proc)
        volume = _parse_volume_text(proc.stdout)
        if volume is None:
            volume = _parse_volume_text(proc.stderr)
    return volume, history


def _set_transport_volume(
    path: str, value: int
) -> tuple[bool, int | None, subprocess.CompletedProcess]:
    proc = _bluetoothctl_script(f"menu transport", f"volume {path} {value}")
    if proc.returncode != 0:
        return False, None, proc
    volume = _parse_volume_text(proc.stdout)
    if volume is None:
        volume = _parse_volume_text(proc.stderr)
    return True, volume, proc


def _run_volume_action(action: str) -> tuple[bool, str]:
    try:
        transport, list_proc = _pick_transport_path()
    except FileNotFoundError as exc:
        return False, f"bluetoothctl introuvable: {exc}"
    except subprocess.TimeoutExpired:
        return False, "Commande bluetoothctl expirée"
    except Exception:
        servo_logger.logger.exception("VOLUME_TRANSPORT_LIST_FAILURE")
        return False, "Erreur bluetoothctl (voir logs)"

    if not transport:
        detail = ((list_proc.stdout or "") + (list_proc.stderr or "")).strip()
        if detail:
            servo_logger.logger.warning("VOLUME_NO_TRANSPORT | output=%s", detail)
        return False, "Aucun transport bluetooth actif (périphérique connecté ?)"

    try:
        current, history = _get_transport_volume(transport)
    except subprocess.TimeoutExpired:
        return False, "Lecture du volume bluetooth expirée"
    except Exception:
        servo_logger.logger.exception("VOLUME_READ_ERROR")
        return False, "Lecture du volume bluetooth impossible"

    if current is None:
        for idx, proc in enumerate(history):
            servo_logger.logger.warning(
                "VOLUME_READ_OUTPUT[%s] | code=%s | stdout=%s | stderr=%s",
                idx,
                proc.returncode,
                (proc.stdout or "").strip(),
                (proc.stderr or "").strip(),
            )
        return False, "Impossible de lire le volume bluetooth"

    if current == 0 and action in ("up", "down"):
        resume_proc = _bluetoothctl_script("menu player", "play")
        resume_stdout = (resume_proc.stdout or "").strip()
        resume_stderr = (resume_proc.stderr or "").strip()
        servo_logger.logger.debug(
            "VOLUME_RESUME_ATTEMPT | code=%s | stdout=%s | stderr=%s",
            resume_proc.returncode,
            resume_stdout,
            resume_stderr,
        )
        if resume_proc.returncode != 0:
            return False, "Impossible de réactiver le transport bluetooth"
        try:
            current, history = _get_transport_volume(transport)
        except subprocess.TimeoutExpired:
            return False, "Lecture du volume bluetooth expirée"
        except Exception:
            servo_logger.logger.exception("VOLUME_READ_ERROR_POST_RESUME")
            return False, "Lecture du volume bluetooth impossible"
        if current is None:
            return False, "Impossible de lire le volume bluetooth"
    target = current
    if action == "up":
        target = min(VOLUME_MAX, current + VOLUME_STEP)
        if target == current:
            return True, f"Volume déjà au maximum ({current})"
    elif action == "down":
        target = max(0, current - VOLUME_STEP)
        if target == current:
            return True, f"Volume déjà au minimum ({current})"
    elif action == "mute":
        if current == 0:
            return True, "Volume déjà à 0"
        target = 0
    else:
        return False, "Unknown volume action"

    try:
        success, applied, proc = _set_transport_volume(transport, target)
    except subprocess.TimeoutExpired:
        return False, "Réglage du volume bluetooth expiré"
    except Exception:
        servo_logger.logger.exception("VOLUME_WRITE_ERROR")
        return False, "Réglage du volume bluetooth impossible"

    if not success:
        detail = ((proc.stderr or "") or (proc.stdout or "")).strip()
        servo_logger.logger.warning(
            "VOLUME_SET_FAILED | code=%s | output=%s", proc.returncode, detail
        )
        return False, detail or "Commande volume bluetoothctl refusée"

    applied_value = applied if applied is not None else target
    servo_logger.logger.debug(
        "VOLUME_SET | action=%s | transport=%s | from=%s | to=%s",
        action,
        transport,
        current,
        applied_value,
    )
    if action == "mute":
        return True, "Volume coupé"
    return True, f"Volume réglé à {applied_value}"


# --- Channels (default: all enabled)
CHANNELS_DEFAULT = {"eye_left": True, "eye_right": True, "neck": True, "jaw": True}
player_channels = CHANNELS_DEFAULT.copy()
# expose to player if it supports it
setattr(player, "channels", player_channels)


# --- Playlist (in-memory) ---
class PlaylistManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: list[dict[str, Any]] = []
        self._id_seq = count(1)

    def add(self, session: str) -> tuple[dict[str, Any], int]:
        with self._lock:
            item = {
                "id": next(self._id_seq),
                "session": session,
                "added_at": time.time(),
                "retries": 0,
            }
            self._queue.append(item)
            return item.copy(), len(self._queue)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [item.copy() for item in self._queue]

    def pop_next(self) -> Optional[dict[str, Any]]:
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.pop(0)
            return item.copy()

    def remove(self, item_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            for idx, item in enumerate(self._queue):
                if item["id"] == item_id:
                    removed = self._queue.pop(idx)
                    return removed.copy()
        return None

    def move(self, item_id: int, offset: int) -> str:
        with self._lock:
            for idx, item in enumerate(self._queue):
                if item["id"] == item_id:
                    new_idx = max(0, min(len(self._queue) - 1, idx + offset))
                    if new_idx == idx:
                        return "noop"
                    self._queue.pop(idx)
                    self._queue.insert(new_idx, item)
                    return "moved"
        return "not_found"

    def push_front(self, item: dict[str, Any]) -> None:
        with self._lock:
            self._queue.insert(0, item.copy())

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def has_items(self) -> bool:
        with self._lock:
            return bool(self._queue)


playlist = PlaylistManager()
_current_entry_lock = threading.Lock()
_current_entry: Optional[dict[str, Any]] = None


def _set_current_entry(entry: Optional[dict[str, Any]]) -> None:
    global _current_entry
    with _current_entry_lock:
        _current_entry = entry.copy() if entry else None


def _get_current_entry() -> Optional[dict[str, Any]]:
    with _current_entry_lock:
        if _current_entry is None:
            return None
        return _current_entry.copy()


def _ensure_session_exists(session_name: str) -> Path:
    session_dir = DATA_DIR / session_name
    if not session_dir.exists() or not session_dir.is_dir():
        raise ValueError(f"Session introuvable: {session_name}")

    json_files = list(session_dir.glob("*.json"))
    mp3_files = list(session_dir.glob("*.mp3"))
    if not json_files:
        raise ValueError("Fichier JSON introuvable dans la session")
    if not mp3_files:
        raise ValueError("Fichier MP3 introuvable dans la session")
    return session_dir


def _start_session(
    session_name: str, source: str, item_id: Optional[int] = None
) -> bool:
    try:
        session_dir = _ensure_session_exists(session_name)
    except ValueError as exc:
        servo_logger.logger.error(
            f"PLAYLIST_INVALID | session={session_name} | reason={exc}"
        )
        return False

    try:
        player.load(session_dir)
        player.play()
    except Exception as exc:
        servo_logger.logger.error(
            f"PLAYLIST_START_FAILED | session={session_name} | error={exc}"
        )
        return False

    _set_current_entry(
        {
            "session": session_name,
            "id": item_id,
            "source": source,
            "started_at": time.time(),
        }
    )
    servo_logger.logger.info(
        f"PLAYLIST_START | session={session_name} | source={source} | id={item_id}"
    )
    return True


def _start_next_from_playlist() -> None:
    while True:
        next_item = playlist.pop_next()
        if not next_item:
            return
        if _start_session(next_item["session"], "playlist", next_item["id"]):
            return
        retries = int(next_item.get("retries", 0)) + 1
        next_item["retries"] = retries
        servo_logger.logger.warning(
            f"PLAYLIST_SKIP_FAILED | session={next_item['session']} | retry={retries}"
        )
        if retries >= 5:
            servo_logger.logger.error(
                f"PLAYLIST_DROP | session={next_item['session']} | retries={retries}"
            )
            continue
        playlist.push_front(next_item)
        delay = min(0.5 * retries, 3.0)
        threading.Timer(delay, _ensure_playback_running).start()
        return


def _ensure_playback_running() -> None:
    try:
        active = player.status().get("running", False)
    except Exception:
        active = False
    if active or _get_current_entry() is not None:
        return
    _start_next_from_playlist()


def _handle_track_finished(
    reason: str, error: Optional[str], session_name: Optional[str]
) -> None:
    current = _get_current_entry()
    log_bits = [f"reason={reason}"]
    if session_name:
        log_bits.append(f"session={session_name}")
    if error:
        log_bits.append(f"error={error}")
    servo_logger.logger.info("PLAYLIST_FINISHED | " + " | ".join(log_bits))

    if reason != "replace":
        _set_current_entry(None)

    if reason in {"completed", "skip", "error"}:
        threading.Thread(target=_start_next_from_playlist, daemon=True).start()


player.set_on_track_finished(_handle_track_finished)


def _clamp_pitch_offset(value: float) -> float:
    return max(-45.0, min(45.0, value))


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".pitch_tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        shutil.move(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass


def save_pitch_offsets() -> None:
    offsets = {name: spec.pitch_offset for name, spec in player.hw.SPECS.items()}
    _write_json_atomic(PITCH_CONFIG_PATH, offsets)


def load_pitch_offsets() -> None:
    if not PITCH_CONFIG_PATH.exists():
        return
    try:
        with open(PITCH_CONFIG_PATH, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except Exception as exc:
        servo_logger.logger.warning(f"PITCH_LOAD_FAILED | {exc}")
        return

    if not isinstance(stored, dict):
        servo_logger.logger.warning("PITCH_LOAD_FAILED | Invalid format")
        return

    for servo_name, raw_value in stored.items():
        if servo_name not in player.hw.SPECS:
            continue
        try:
            offset = _clamp_pitch_offset(float(raw_value))
        except (TypeError, ValueError):
            continue
        player.hw.set_pitch_offset(servo_name, offset)


def save_channel_flags() -> None:
    _write_json_atomic(CHANNELS_CONFIG_PATH, player_channels)


def load_channel_flags() -> None:
    if not CHANNELS_CONFIG_PATH.exists():
        return
    try:
        with open(CHANNELS_CONFIG_PATH, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except Exception as exc:
        servo_logger.logger.warning(f"CHANNELS_LOAD_FAILED | {exc}")
        return

    if not isinstance(stored, dict):
        servo_logger.logger.warning("CHANNELS_LOAD_FAILED | Invalid format")
        return

    updated = {}
    for name in CHANNELS_DEFAULT:
        value = stored.get(name)
        if isinstance(value, bool):
            updated[name] = value
    if not updated:
        return

    player_channels.update(updated)
    setattr(player, "channels", player_channels)
    if hasattr(player, "set_channels") and callable(player.set_channels):
        player.set_channels(player_channels)


load_pitch_offsets()
load_channel_flags()


def sanitize_scene_name(name: str) -> str:
    """Nettoie le nom de scène pour créer un nom de répertoire valide"""
    if not name or not name.strip():
        raise ValueError("Nom de scène requis")

    # Supprimer espaces et caractères spéciaux, garder uniquement alphanum + _ -
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", name.strip().replace(" ", ""))

    if not sanitized:
        raise ValueError("Nom de scène invalide après nettoyage")

    return sanitized[:50]  # Limiter la longueur


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        app.static_folder, "SkullPlayer.png", mimetype="image/png"
    )


@app.route("/upload", methods=["POST"])
def upload():
    try:
        files = request.files
        if "json" not in files or "mp3" not in files:
            return jsonify({"error": "Fichiers json et mp3 requis"}), 400

        # Récupérer le nom de scène du formulaire
        scene_name = request.form.get("scene_name", "").strip()
        if not scene_name:
            return jsonify({"error": "Nom de scène requis"}), 400

        # Nettoyer le nom de scène
        try:
            clean_name = sanitize_scene_name(scene_name)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Créer le répertoire avec le nom nettoyé
        session_dir = DATA_DIR / clean_name

        # Vérifier si le répertoire existe déjà
        if session_dir.exists():
            return jsonify({"error": f"Une session '{clean_name}' existe déjà"}), 409

        session_dir.mkdir(parents=True)

        # Sauvegarder les fichiers avec leurs nouveaux noms
        json_file = files["json"]
        mp3_file = files["mp3"]

        # Les fichiers arrivent déjà renommés côté client
        json_filename = json_file.filename or "timeline.json"
        mp3_filename = mp3_file.filename or "audio.mp3"

        json_file.save(session_dir / json_filename)
        mp3_file.save(session_dir / mp3_filename)

        return jsonify(
            {
                "session": clean_name,
                "message": f"Session '{scene_name}' créée avec succès",
                "files": {"json": json_filename, "mp3": mp3_filename},
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erreur lors de l'upload: {str(e)}"}), 500


@app.route("/sessions")
def sessions():
    try:
        sessions_list = [d.name for d in sorted(DATA_DIR.iterdir()) if d.is_dir()]
        return jsonify({"sessions": sessions_list})
    except Exception as e:
        return jsonify({"error": f"Erreur lors du listage: {str(e)}"}), 500


@app.route("/play", methods=["POST"])
def play():
    try:
        body = request.get_json(silent=True) or {}
        sid = body.get("session")
        if not sid:
            return jsonify({"error": "Champ 'session' manquant"}), 400

        try:
            _ensure_session_exists(sid)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404

        status_info = player.status()
        is_running = bool(status_info.get("running"))
        if is_running:
            item, position = playlist.add(sid)
            servo_logger.logger.info(
                f"PLAYLIST_ENQUEUE | session={sid} | trigger=play_button | position={position}"
            )
            return (
                jsonify(
                    {
                        "status": "queued",
                        "session": sid,
                        "position": position,
                        "item": item,
                    }
                ),
                202,
            )

        if not _start_session(sid, "manual"):
            servo_logger.logger.error(f"PLAY_START_FAILED | session={sid}")
            _ensure_playback_running()
            return jsonify({"error": "Impossible de demarrer la lecture"}), 500

        return jsonify({"status": "playing", "session": sid})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Impossible de demarrer la lecture: {e}"}), 400


@app.route("/pause", methods=["POST"])
def pause():
    try:
        player.pause()
        return jsonify({"status": "paused"})
    except Exception as e:
        return jsonify({"error": f"Erreur pause: {e}"}), 500


@app.route("/resume", methods=["POST"])
def resume():
    try:
        player.resume()
        return jsonify({"status": "resumed"})
    except Exception as e:
        return jsonify({"error": f"Erreur resume: {e}"}), 500


@app.route("/stop", methods=["POST"])
def stop():
    try:
        player.stop()
        _set_current_entry(None)
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": f"Erreur stop: {e}"}), 500


@app.route("/status")
def status():
    try:
        # expose channels in status as well
        st = player.status()
        st["channels"] = dict(player_channels)
        st["playlist_size"] = playlist.size()
        st["current_playlist"] = _get_current_entry()
        return jsonify(st)
    except Exception as e:
        return jsonify({"error": f"Erreur status: {e}"}), 500


@app.route("/volume", methods=["POST"])
def volume():
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").lower()
    if action not in VOLUME_ACTIONS:
        return jsonify({"error": "Unknown volume action"}), 400

    ok, message = _run_volume_action(action)
    response = {"action": action, "ok": ok}
    if message:
        response["message"] = message
    status = 200 if ok else 500
    return jsonify(response), status


@app.route("/playlist", methods=["GET", "POST"])
def playlist_api():
    try:
        if request.method == "GET":
            return jsonify(
                {
                    "current": _get_current_entry(),
                    "queue": playlist.snapshot(),
                }
            )

        body = request.get_json(silent=True) or {}
        session = body.get("session")
        if not session:
            return jsonify({"error": "Champ 'session' manquant"}), 400

        try:
            _ensure_session_exists(session)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404

        item, position = playlist.add(session)
        servo_logger.logger.info(
            f"PLAYLIST_ENQUEUE | session={session} | trigger=api | position={position}"
        )

        _ensure_playback_running()

        current = _get_current_entry()
        status = "queued"
        http_code = 201
        if current and current.get("id") == item["id"]:
            status = "playing"
            http_code = 200

        return (
            jsonify(
                {
                    "status": status,
                    "item": item,
                    "position": position,
                    "current": current,
                }
            ),
            http_code,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erreur playlist: {e}"}), 500


@app.route("/playlist/<int:item_id>", methods=["DELETE"])
def playlist_delete(item_id: int):
    removed = playlist.remove(item_id)
    if not removed:
        return jsonify({"error": "Element introuvable"}), 404
    servo_logger.logger.info(
        f"PLAYLIST_REMOVE | id={item_id} | session={removed['session']}"
    )
    return jsonify({"status": "removed", "item": removed})


@app.route("/playlist/<int:item_id>/move", methods=["POST"])
def playlist_move(item_id: int):
    body = request.get_json(silent=True) or {}
    direction = (body.get("direction") or "").lower()
    if direction not in {"up", "down"}:
        return jsonify({"error": "Direction invalide"}), 400

    offset = -1 if direction == "up" else 1
    outcome = playlist.move(item_id, offset)
    if outcome == "not_found":
        return jsonify({"error": "Element introuvable"}), 404
    if outcome == "noop":
        return jsonify({"status": "noop"})

    servo_logger.logger.info(f"PLAYLIST_MOVE | id={item_id} | direction={direction}")
    return jsonify({"status": "moved", "direction": direction})


@app.route("/playlist/skip", methods=["POST"])
def playlist_skip():
    try:
        status_info = player.status()
        if status_info.get("running"):
            servo_logger.logger.info("PLAYLIST_SKIP_REQUEST | state=running")
            player.stop(reason="skip")
            return jsonify({"status": "skipping"})

        servo_logger.logger.info("PLAYLIST_SKIP_REQUEST | state=idle")
        _ensure_playback_running()
        current = _get_current_entry()
        if current:
            return jsonify({"status": "playing", "current": current})
        return jsonify({"status": "idle"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erreur skip: {e}"}), 500


# -------------------- Channels API --------------------
@app.route("/channels", methods=["GET", "POST"])
def channels():
    global player_channels
    try:
        if request.method == "GET":
            return jsonify(player_channels)

        # POST: update flags
        body = request.get_json(silent=True) or {}

        def as_bool(x, default=True):
            if isinstance(x, bool):
                return x
            if isinstance(x, (int, float)):
                return bool(x)
            if isinstance(x, str):
                return x.strip().lower() in ("1", "true", "on", "yes")
            return default

        new_flags = {
            "eye_left": as_bool(
                body.get("eye_left", player_channels["eye_left"]),
                player_channels["eye_left"],
            ),
            "eye_right": as_bool(
                body.get("eye_right", player_channels["eye_right"]),
                player_channels["eye_right"],
            ),
            "neck": as_bool(
                body.get("neck", player_channels["neck"]), player_channels["neck"]
            ),
            "jaw": as_bool(
                body.get("jaw", player_channels["jaw"]), player_channels["jaw"]
            ),
        }
        player_channels.update(new_flags)

        # reflect on player
        setattr(player, "channels", player_channels)

        # if SyncPlayer has set_channels method, call it
        if hasattr(player, "set_channels") and callable(player.set_channels):
            player.set_channels(player_channels)

        save_channel_flags()

        return jsonify(player_channels)

    except Exception as e:
        return jsonify({"error": f"Erreur channels: {e}"}), 500


@app.route("/pitch", methods=["GET", "POST"])
def pitch():
    """Gestion des offsets de pitch par servo"""
    try:
        if request.method == "GET":
            # Retourner les offsets actuels
            offsets = {}
            for name, spec in player.hw.SPECS.items():
                offsets[name] = spec.pitch_offset
            return jsonify(offsets)

        # POST: mettre à jour les offsets
        body = request.get_json(silent=True) or {}

        for servo_name in ["jaw", "eye_left", "eye_right", "neck_pan"]:
            if servo_name in body:
                try:
                    offset = _clamp_pitch_offset(float(body[servo_name]))
                except (ValueError, TypeError):
                    continue
                player.hw.set_pitch_offset(servo_name, offset)

        save_pitch_offsets()

        # Retourner les nouveaux offsets
        # Retourner les nouveaux offsets
        offsets = {}
        for name, spec in player.hw.SPECS.items():
            offsets[name] = spec.pitch_offset
        return jsonify(offsets)

    except Exception as e:
        return jsonify({"error": f"Erreur pitch: {e}"}), 500


# -------------------- Logs API --------------------
@app.route("/logs")
def logs():
    """Retourne les logs servo en temps réel"""
    try:
        log_file = servo_logger.get_latest_log_file()
        if not log_file.exists():
            return jsonify({"error": "Aucun fichier de log trouvé"}), 404

        # Lire les dernières lignes (tail)
        lines = request.args.get("lines", "100", type=int)
        lines = max(1, min(1000, lines))  # Limiter entre 1 et 1000 lignes

        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return jsonify(
            {
                "file": str(log_file),
                "total_lines": len(all_lines),
                "returned_lines": len(recent_lines),
                "lines": [line.rstrip() for line in recent_lines],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/logs/stream")
def logs_stream():
    """Stream des logs en temps réel via Server-Sent Events"""

    def generate():
        log_file = servo_logger.get_latest_log_file()
        if not log_file.exists():
            yield "data: No log file found\n\n"
            return

        # Commencer à la fin du fichier
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                # Aller à la fin
                f.seek(0, 2)

                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.rstrip()}\n\n"
                    else:
                        time.sleep(0.1)  # Attendre nouvelles données
        except Exception as e:
            yield f"data: Error reading log: {e}\n\n"

    return Response(generate(), mimetype="text/plain")


@app.route("/logs/stats")
def logs_stats():
    """Retourne les statistiques des dernières sessions"""
    try:
        stats_dir = Path("logs")
        stats_files = list(stats_dir.glob("session_stats_*.json"))
        stats_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Retourner les 10 dernières sessions
        recent_stats = []
        for stats_file in stats_files[:10]:
            try:
                import json

                with open(stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                recent_stats.append(stats)
            except Exception as e:
                continue

        return jsonify(
            {"total_sessions": len(stats_files), "recent_sessions": recent_stats}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Serve uploaded files for debug
@app.route("/data/<path:filename>")
def data_file(filename):
    return send_from_directory(DATA_DIR, filename)


# Serve log files for download
@app.route("/logs/download")
def logs_download():
    """Télécharge le fichier de log actuel"""
    try:
        log_file = servo_logger.get_latest_log_file()
        if not log_file.exists():
            return "No log file found", 404
        return send_from_directory(log_file.parent, log_file.name, as_attachment=True)
    except Exception as e:
        return f"Error: {e}", 500


if __name__ == "__main__":
    print("Servo Sync Player - Web Interface")
    print(f"Logs directory: {servo_logger.log_dir}")
    print(f"Current log file: {servo_logger.get_latest_log_file()}")
    print("Available endpoints:")
    print("  - Main interface: http://localhost:5000")
    print("  - /logs        : Get recent log lines (JSON)")
    print("  - /logs/stream : Real-time log stream")
    print("  - /logs/stats  : Session statistics")
    print("  - /logs/download : Download log file")
    app.run(host="0.0.0.0", port=5000, debug=True)
