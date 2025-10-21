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
import random
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
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from flask import (
    Flask,
    request,
    render_template,
    send_from_directory,
    jsonify,
    Response,
)

from typing import Any, Dict, Iterable, Optional, Tuple

from pydub import AudioSegment
from sync_player import SyncPlayer
from logger import servo_logger

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(exist_ok=True)
PITCH_CONFIG_PATH = CONFIG_DIR / "pitch_offsets.json"
CHANNELS_CONFIG_PATH = CONFIG_DIR / "channels_state.json"
ESP32_CONFIG_PATH = CONFIG_DIR / "esp32_settings.json"
SESSION_CATEGORIES_PATH = CONFIG_DIR / "session_categories.json"
ESP32_BUTTON_ASSIGNMENTS_PATH = CONFIG_DIR / "esp32_button_categories.json"


app = Flask(__name__, static_folder="static", template_folder="templates")
player = SyncPlayer()

VOLUME_TIMEOUT = float(os.environ.get("PLAYLIST_VOLUME_TIMEOUT", "5"))
VOLUME_STEP = int(os.environ.get("PLAYLIST_VOLUME_STEP", "8"))
VOLUME_MAX = int(os.environ.get("PLAYLIST_VOLUME_MAX", "127"))
VOLUME_TOOL = os.environ.get("PLAYLIST_VOLUME_CLI", "bluetoothctl")
_VOLUME_CMD_BASE = shlex.split(VOLUME_TOOL) if VOLUME_TOOL else ["bluetoothctl"]
if not _VOLUME_CMD_BASE:
    _VOLUME_CMD_BASE = ["bluetoothctl"]

ESP32_DEFAULT_CONFIG = {"host": "", "port": 80, "enabled": False}
ESP32_BUTTON_COUNT = 3
ESP32_HTTP_TIMEOUT = float(os.environ.get("PLAYLIST_ESP32_TIMEOUT", "3.0"))

VOLUME_ACTIONS = {"up", "down", "mute", "set"}

_SESSION_CATEGORY_DEFAULTS = {
    "categories": ["enfant", "adulte"],
    "sessions": {},
}
_session_categories_lock = threading.Lock()
_session_categories_cache: Optional[dict[str, Any]] = None
_esp32_button_assignments_lock = threading.Lock()

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

_TRANSPORT_RE = re.compile(r"^Transport\s+(/[^\s]+)", re.MULTILINE)
_VOLUME_RE = re.compile(r"\s*Volume:\s*(?:0x[0-9A-Fa-f]+\s*)?(?:\((\d+)\)|(\d+))")
_BT_CONNECTED_RE = re.compile(r"\bConnected:\s*(yes|no)\b", re.IGNORECASE)

BT_DEVICE_ADDR = os.environ.get("PLAYLIST_BT_DEVICE_ADDR", "").strip().upper()
_DEFAULT_RESTART_CMD = "sudo systemctl restart servo-sync.service"
_SERVICE_RESTART_RAW = os.environ.get(
    "PLAYLIST_SERVICE_RESTART_CMD", _DEFAULT_RESTART_CMD
).strip()
SERVICE_RESTART_CMD = shlex.split(_SERVICE_RESTART_RAW) if _SERVICE_RESTART_RAW else []
SERVICE_RESTART_TIMEOUT = float(
    os.environ.get("PLAYLIST_SERVICE_RESTART_TIMEOUT", "15")
)

_DEFAULT_BLUETOOTH_RESTART_CMD = "sudo systemctl restart bluetooth.service"
_BLUETOOTH_RESTART_RAW = os.environ.get(
    "PLAYLIST_BLUETOOTH_RESTART_CMD", _DEFAULT_BLUETOOTH_RESTART_CMD
).strip()
BLUETOOTH_RESTART_CMD = (
    shlex.split(_BLUETOOTH_RESTART_RAW) if _BLUETOOTH_RESTART_RAW else []
)
BLUETOOTH_RESTART_TIMEOUT = float(
    os.environ.get("PLAYLIST_BLUETOOTH_RESTART_TIMEOUT", "15")
)


def _client_request_metadata() -> dict[str, str]:
    """Extract request origin details for logging."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    primary_forward = (
        forwarded_for.split(",")[0].strip() if forwarded_for else None
    )
    remote_addr = primary_forward or request.remote_addr or ""
    user_agent = request.headers.get("User-Agent") or ""
    return {
        "client_ip": remote_addr or "-",
        "forwarded_for": forwarded_for or "-",
        "user_agent": user_agent or "-",
    }


def _format_log_payload(payload: Any, limit: int = 200) -> str:
    """Serialize payload content for concise log output."""
    try:
        serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    except Exception:
        serialized = str(payload)
    if len(serialized) > limit:
        return serialized[: limit - 3] + "..."
    return serialized


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


def _bluetooth_info(address: str) -> dict[str, Any] | None:
    if not address:
        return None
    try:
        proc = _bluetoothctl_script(f"info {address}")
    except subprocess.TimeoutExpired:
        servo_logger.logger.warning("BTCTL_INFO_TIMEOUT | address=%s", address)
        return None
    except Exception:
        servo_logger.logger.exception("BTCTL_INFO_ERROR | address=%s", address)
        return None

    if proc.returncode != 0:
        servo_logger.logger.warning(
            "BTCTL_INFO_FAILED | address=%s | code=%s | stderr=%s",
            address,
            proc.returncode,
            (proc.stderr or "").strip(),
        )
        return None

    stdout = proc.stdout or ""
    connected = None
    match = _BT_CONNECTED_RE.search(stdout)
    if match:
        connected = match.group(1).lower() == "yes"

    return {"connected": connected, "raw": stdout}


def _ensure_bt_connection(address: str) -> bool:
    if not address:
        return True

    info = _bluetooth_info(address)
    if info and info.get("connected") is True:
        return True

    servo_logger.logger.warning("BTCTL_RECONNECT_ATTEMPT | address=%s", address)
    try:
        proc = _bluetoothctl_script(f"connect {address}")
    except subprocess.TimeoutExpired:
        servo_logger.logger.error("BTCTL_CONNECT_TIMEOUT | address=%s", address)
        return False
    except Exception:
        servo_logger.logger.exception("BTCTL_CONNECT_ERROR | address=%s", address)
        return False

    if proc.returncode != 0:
        servo_logger.logger.error(
            "BTCTL_CONNECT_FAILED | address=%s | code=%s | stderr=%s",
            address,
            proc.returncode,
            (proc.stderr or "").strip(),
        )
        return False

    time.sleep(0.5)
    info_after = _bluetooth_info(address)
    if info_after and info_after.get("connected") is True:
        servo_logger.logger.info("BTCTL_RECONNECT_SUCCESS | address=%s", address)
        return True

    servo_logger.logger.error(
        "BTCTL_RECONNECT_UNCONFIRMED | address=%s | stdout=%s",
        address,
        (info_after or {}).get("raw", "")[:200],
    )
    return False


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


def _run_volume_action(action: str, target_value: int | None = None) -> tuple[bool, str, int | None]:
    try:
        transport, list_proc = _pick_transport_path()
    except FileNotFoundError as exc:
        return False, f"bluetoothctl introuvable: {exc}", None
    except subprocess.TimeoutExpired:
        return False, "Commande bluetoothctl expiree", None
    except Exception:
        servo_logger.logger.exception("VOLUME_TRANSPORT_LIST_FAILURE")
        return False, "Erreur bluetoothctl (voir logs)", None

    if not transport:
        detail = ((list_proc.stdout or "") + (list_proc.stderr or "")).strip()
        if BT_DEVICE_ADDR:
            if _ensure_bt_connection(BT_DEVICE_ADDR):
                transport, list_proc = _pick_transport_path()
        if not transport:
            if detail:
                servo_logger.logger.warning("VOLUME_NO_TRANSPORT | output=%s", detail)
            return False, "Aucun transport bluetooth actif (peripherique connecte ?)", None

    try:
        current, history = _get_transport_volume(transport)
    except subprocess.TimeoutExpired:
        return False, "Lecture du volume bluetooth expiree", None
    except Exception:
        servo_logger.logger.exception("VOLUME_READ_ERROR")
        return False, "Lecture du volume bluetooth impossible", None

    if current is None:
        for idx, proc in enumerate(history):
            servo_logger.logger.warning(
                "VOLUME_READ_OUTPUT[%s] | code=%s | stdout=%s | stderr=%s",
                idx,
                proc.returncode,
                (proc.stdout or "").strip(),
                (proc.stderr or "").strip(),
            )
        return False, "Impossible de lire le volume bluetooth", None

    if not isinstance(current, (int, float)):
        return False, "Impossible de lire le volume bluetooth", None

    current_value = int(round(current))

    resume_needed = False
    if current_value == 0:
        if action in ("up", "down"):
            resume_needed = True
        elif action == "set" and target_value is not None:
            try:
                resume_target = int(float(target_value))
            except (TypeError, ValueError):
                resume_target = 0
            if resume_target > 0:
                resume_needed = True

    if resume_needed:
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
            return False, "Impossible de reactiver le transport bluetooth", None
        try:
            current, history = _get_transport_volume(transport)
        except subprocess.TimeoutExpired:
            return False, "Lecture du volume bluetooth expiree", None
        except Exception:
            servo_logger.logger.exception("VOLUME_READ_ERROR_POST_RESUME")
            return False, "Lecture du volume bluetooth impossible", None
        if current is None or not isinstance(current, (int, float)):
            return False, "Impossible de lire le volume bluetooth", None
        current_value = int(round(current))

    target = current_value
    if action == "up":
        target = min(VOLUME_MAX, current_value + VOLUME_STEP)
        if target == current_value:
            return True, f"Volume deja au maximum ({current_value})", current_value
    elif action == "down":
        target = max(0, current_value - VOLUME_STEP)
        if target == current_value:
            return True, f"Volume deja au minimum ({current_value})", current_value
    elif action == "mute":
        if current_value == 0:
            return True, "Volume deja a 0", 0
        target = 0
    elif action == "set":
        if target_value is None:
            return False, "Valeur volume manquante", None
        try:
            target_int = int(float(target_value))
        except (TypeError, ValueError):
            return False, "Valeur volume invalide", None
        target_int = max(0, min(VOLUME_MAX, target_int))
        target = target_int
        if target_int == current_value:
            return True, f"Volume deja a {target_int}", target_int
    else:
        return False, "Unknown volume action", None

    try:
        success, applied, proc = _set_transport_volume(transport, int(target))
    except subprocess.TimeoutExpired:
        return False, "Reglage du volume bluetooth expire", None
    except Exception:
        servo_logger.logger.exception("VOLUME_WRITE_ERROR")
        return False, "Reglage du volume bluetooth impossible", None

    if not success:
        detail = ((proc.stderr or "") or (proc.stdout or "")).strip()
        servo_logger.logger.warning(
            "VOLUME_SET_FAILED | code=%s | output=%s", proc.returncode, detail
        )
        return False, detail or "Commande volume bluetoothctl refusee", None

    applied_source = applied if isinstance(applied, (int, float)) else target
    applied_value = int(round(applied_source))
    servo_logger.logger.debug(
        "VOLUME_SET | action=%s | transport=%s | from=%s | to=%s",
        action,
        transport,
        current_value,
        applied_value,
    )
    if action == "mute":
        return True, "Volume coupe", applied_value
    return True, f"Volume regle a {applied_value}", applied_value


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

    def purge_session(self, session: str) -> list[dict[str, Any]]:
        """Remove every queued entry matching the given session name."""
        removed: list[dict[str, Any]] = []
        with self._lock:
            kept: list[dict[str, Any]] = []
            for item in self._queue:
                if item.get("session") == session:
                    removed.append(item.copy())
                else:
                    kept.append(item)
            self._queue = kept
        return removed

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

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def has_items(self) -> bool:
        with self._lock:
            return bool(self._queue)


playlist = PlaylistManager()
_current_entry_lock = threading.Lock()
_current_entry: Optional[dict[str, Any]] = None


# Keep ESP32 relay active for a brief window while the next track loads
TRANSITION_HOLD_SECONDS = float(os.environ.get("PLAYLIST_TRANSITION_HOLD", "4.0"))
_TRANSITION_HOLD_REASONS = {"completed", "skip"}
_transition_state_lock = threading.Lock()
_last_finish_ts: float = 0.0
_last_finish_reason: Optional[str] = None


def _set_current_entry(entry: Optional[dict[str, Any]]) -> None:
    global _current_entry
    with _current_entry_lock:
        _current_entry = entry.copy() if entry else None


def _get_current_entry() -> Optional[dict[str, Any]]:
    with _current_entry_lock:
        if _current_entry is None:
            return None
        return _current_entry.copy()


_random_lock = threading.Lock()
_RANDOM_EXCLUDED_NAMES = {"accueil"}
_random_enabled = False
_random_last_pick: Optional[dict[str, Any]] = None


def _normalize_session_name(name: str) -> str:
    return name.strip().lower()


def _list_session_names() -> list[str]:
    try:
        entries = sorted(DATA_DIR.iterdir(), key=lambda p: p.name.lower())
    except FileNotFoundError:
        return []
    except Exception as exc:
        servo_logger.logger.warning("SESSION_LIST_FAILED | error=%s", exc)
        return []

    sessions: list[str] = []
    for entry in entries:
        if entry.is_dir():
            sessions.append(entry.name)
    return sessions


def _eligible_random_sessions(additional_excludes: Iterable[str] = ()) -> list[str]:
    excluded = {_normalize_session_name(name) for name in _RANDOM_EXCLUDED_NAMES}
    for name in additional_excludes:
        if name:
            excluded.add(_normalize_session_name(name))

    candidates: list[str] = []
    for session_name in _list_session_names():
        if _normalize_session_name(session_name) in excluded:
            continue
        candidates.append(session_name)
    return candidates


def _pick_random_session(additional_excludes: Iterable[str] = ()) -> Optional[str]:
    candidates = _eligible_random_sessions(additional_excludes)
    if not candidates:
        return None
    return random.choice(candidates)


def _is_random_mode_enabled() -> bool:
    with _random_lock:
        return _random_enabled


def _set_random_mode_enabled(enabled: bool) -> bool:
    global _random_enabled, _random_last_pick
    with _random_lock:
        changed = _random_enabled != enabled
        _random_enabled = enabled
        if not enabled:
            _random_last_pick = None
        return changed


def _random_mode_snapshot() -> dict[str, Any]:
    with _random_lock:
        snapshot = {"enabled": _random_enabled}
        if _random_last_pick is not None:
            snapshot["last_pick"] = _random_last_pick.copy()
        else:
            snapshot["last_pick"] = None
    return snapshot


def _record_random_pick(selected: str, requested: Optional[str]) -> None:
    global _random_last_pick
    with _random_lock:
        _random_last_pick = {
            "session": selected,
            "requested": requested,
            "timestamp": time.time(),
        }


def _resolve_existing_session_dir(session_name: str) -> Path:
    """Return the session directory ensuring it is inside DATA_DIR."""
    if not session_name:
        raise ValueError("Nom de session invalide")
    data_root = DATA_DIR.resolve()
    try:
        candidate = (DATA_DIR / session_name).resolve(strict=False)
    except Exception as exc:
        raise ValueError("Nom de session invalide") from exc
    if candidate.parent != data_root:
        raise ValueError("Nom de session invalide")
    if not candidate.exists() or not candidate.is_dir():
        raise FileNotFoundError(session_name)
    return candidate


def _ensure_session_exists(session_name: str) -> Path:
    try:
        session_dir = _resolve_existing_session_dir(session_name)
    except FileNotFoundError:
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

    if BT_DEVICE_ADDR:
        if not _ensure_bt_connection(BT_DEVICE_ADDR):
            servo_logger.logger.error(
                "PLAYLIST_BT_RECONNECT_FAILED | session=%s | source=%s",
                session_name,
                source,
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

    global _last_finish_ts, _last_finish_reason
    with _transition_state_lock:
        _last_finish_ts = time.time()
        _last_finish_reason = reason

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


def _load_session_categories_locked() -> dict[str, Any]:
    global _session_categories_cache
    if _session_categories_cache is None:
        raw_data: dict[str, Any] = {}
        should_write = False
        if SESSION_CATEGORIES_PATH.exists():
            try:
                with open(SESSION_CATEGORIES_PATH, "r", encoding="utf-8") as handle:
                    raw_data = json.load(handle) or {}
            except Exception:
                servo_logger.logger.exception("SESSION_CATEGORIES_LOAD_FAILED")
                raw_data = {}
                should_write = True
        else:
            should_write = True

        raw_categories = raw_data.get("categories")
        categories: list[str] = []
        if isinstance(raw_categories, list):
            for item in raw_categories:
                text = str(item).strip()
                if text and text not in categories:
                    categories.append(text)
        if not categories:
            categories = list(_SESSION_CATEGORY_DEFAULTS["categories"])
            should_write = True

        raw_sessions = raw_data.get("sessions")
        sessions: dict[str, str] = {}
        if isinstance(raw_sessions, dict):
            for key, value in raw_sessions.items():
                session_name = str(key).strip()
                category_name = str(value).strip()
                if session_name and category_name:
                    sessions[session_name] = category_name
        else:
            should_write = True

        _session_categories_cache = {
            "categories": categories,
            "sessions": sessions,
        }
        if should_write:
            try:
                _write_json_atomic(SESSION_CATEGORIES_PATH, _session_categories_cache)
            except Exception:
                servo_logger.logger.exception("SESSION_CATEGORIES_WRITE_FAILED")
    return _session_categories_cache


def _save_session_categories_locked(
    categories: Iterable[str], sessions: dict[str, str]
) -> dict[str, Any]:
    unique_categories: list[str] = []
    for item in categories:
        text = str(item).strip()
        if text and text not in unique_categories:
            unique_categories.append(text)

    sanitized_sessions: dict[str, str] = {}
    for key, value in sessions.items():
        session_name = str(key).strip()
        category_name = str(value).strip()
        if session_name and category_name:
            sanitized_sessions[session_name] = category_name

    global _session_categories_cache
    _session_categories_cache = {
        "categories": unique_categories,
        "sessions": sanitized_sessions,
    }
    _write_json_atomic(SESSION_CATEGORIES_PATH, _session_categories_cache)

    return {
        "categories": list(unique_categories),
        "sessions": dict(sanitized_sessions),
    }


def _load_session_categories() -> dict[str, Any]:
    with _session_categories_lock:
        cached = _load_session_categories_locked()
        return {
            "categories": list(cached["categories"]),
            "sessions": dict(cached["sessions"]),
        }


def _get_session_category(session_name: Optional[str]) -> Optional[str]:
    if not session_name:
        return None
    data = _load_session_categories()
    return data["sessions"].get(session_name)


def _set_session_category(session_name: str, category: Optional[str]) -> dict[str, Any]:
    normalized_session = (session_name or "").strip()
    if not normalized_session:
        raise ValueError("Nom de session invalide")
    normalized_category = (category or "").strip()
    with _session_categories_lock:
        cached = _load_session_categories_locked()
        categories = list(cached["categories"])
        sessions = dict(cached["sessions"])
        if normalized_category:
            if normalized_category not in categories:
                categories.append(normalized_category)
            sessions[normalized_session] = normalized_category
        else:
            sessions.pop(normalized_session, None)
        return _save_session_categories_locked(categories, sessions)


def _add_category(category: str) -> tuple[dict[str, Any], bool]:
    normalized = (category or "").strip()
    if not normalized:
        raise ValueError("Nom de categorie vide")
    with _session_categories_lock:
        cached = _load_session_categories_locked()
        categories = list(cached["categories"])
        sessions = dict(cached["sessions"])
        if normalized not in categories:
            categories.append(normalized)
            saved = _save_session_categories_locked(categories, sessions)
            return saved, True
        return (
            {
                "categories": list(categories),
                "sessions": dict(sessions),
            },
            False,
        )


def _enrich_entry_with_category(
    entry: Optional[dict[str, Any]], mapping: Optional[dict[str, str]] = None
) -> Optional[dict[str, Any]]:
    if entry is None:
        return None
    result = entry.copy()
    session_name = result.get("session")
    lookup = mapping or _load_session_categories()["sessions"]
    result["category"] = lookup.get(session_name) if session_name else None
    return result


def _enrich_queue_with_categories(
    queue: Iterable[dict[str, Any]], mapping: Optional[dict[str, str]] = None
) -> list[dict[str, Any]]:
    lookup = mapping or _load_session_categories()["sessions"]
    enriched: list[dict[str, Any]] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        enriched.append(_enrich_entry_with_category(item, lookup) or item)
    return enriched


def _default_button_assignments() -> list[str]:
    return ["" for _ in range(ESP32_BUTTON_COUNT)]


def _sanitize_button_assignments(raw: Any) -> list[str]:
    assignments = _default_button_assignments()
    if isinstance(raw, dict):
        raw_values = raw.get("assignments", [])
    elif isinstance(raw, (list, tuple)):
        raw_values = raw
    else:
        raw_values = []

    sanitized: list[str] = []
    for idx in range(ESP32_BUTTON_COUNT):
        value = ""
        if idx < len(raw_values):
            candidate = raw_values[idx]
            if isinstance(candidate, str):
                value = candidate.strip()
        sanitized.append(value)

    while len(sanitized) < ESP32_BUTTON_COUNT:
        sanitized.append("")

    return sanitized[:ESP32_BUTTON_COUNT]


def _load_button_assignments_locked() -> list[str]:
    if not ESP32_BUTTON_ASSIGNMENTS_PATH.exists():
        assignments = _default_button_assignments()
        try:
            _write_json_atomic(
                ESP32_BUTTON_ASSIGNMENTS_PATH, {"assignments": assignments}
            )
        except Exception:
            servo_logger.logger.exception("ESP32_BUTTON_ASSIGNMENTS_INIT_FAILED")
        return assignments

    try:
        with open(ESP32_BUTTON_ASSIGNMENTS_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        servo_logger.logger.exception("ESP32_BUTTON_ASSIGNMENTS_LOAD_FAILED")
        return _default_button_assignments()

    assignments = _sanitize_button_assignments(raw)
    return assignments


def _save_button_assignments_locked(assignments: Iterable[str]) -> list[str]:
    sanitized = _sanitize_button_assignments(list(assignments))
    try:
        _write_json_atomic(
            ESP32_BUTTON_ASSIGNMENTS_PATH, {"assignments": sanitized}
        )
    except Exception:
        servo_logger.logger.exception("ESP32_BUTTON_ASSIGNMENTS_SAVE_FAILED")
    return sanitized


def _load_button_assignments() -> list[str]:
    with _esp32_button_assignments_lock:
        return list(_load_button_assignments_locked())


def _set_button_assignment(index: int, category: str) -> list[str]:
    if index < 0 or index >= ESP32_BUTTON_COUNT:
        raise IndexError("Index bouton hors limites")

    normalized = (category or "").strip()
    with _esp32_button_assignments_lock:
        assignments = _load_button_assignments_locked()
        assignments[index] = normalized
        return _save_button_assignments_locked(assignments)


def _sessions_for_category(category: str) -> list[str]:
    if not category:
        return []
    data = _load_session_categories()
    mapping = data["sessions"]
    normalized = category.strip().lower()
    sessions: list[str] = []
    for name, cat in mapping.items():
        if not name:
            continue
        if (cat or "").strip().lower() == normalized:
            sessions.append(name)
    valid_sessions: list[str] = []
    for session_name in sessions:
        try:
            _ensure_session_exists(session_name)
        except ValueError:
            continue
        valid_sessions.append(session_name)
    return valid_sessions


def _resolve_session_candidate(value: str) -> tuple[str, Optional[str]]:
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError("Session vide")
    matching = _sessions_for_category(candidate)
    if matching:
        return random.choice(matching), candidate
    return candidate, None


def _enqueue_or_play_session(
    session_name: str,
    source: str,
    requested_category: Optional[str] = None,
    log_context: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], int]:
    try:
        _ensure_session_exists(session_name)
    except ValueError as exc:
        return {"error": str(exc)}, 404

    context = log_context or {}
    context_bits = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)

    try:
        status_info = player.status()
    except Exception:
        status_info = {}
    is_running = bool(status_info.get("running"))

    if is_running:
        item, position = playlist.add(session_name)
        enriched_item = _enrich_entry_with_category(item)
        category_label = requested_category or _get_session_category(session_name)
        log_message = f"PLAYLIST_ENQUEUE | session={session_name} | source={source}"
        if context_bits:
            log_message += f" | {context_bits}"
        servo_logger.logger.info(log_message)
        payload = {
            "status": "queued",
            "session": session_name,
            "position": position,
            "item": enriched_item,
            "category": category_label,
            "source": source,
        }
        return payload, 202

    if not _start_session(session_name, source):
        log_message = f"PLAY_START_FAILED | session={session_name} | source={source}"
        if context_bits:
            log_message += f" | {context_bits}"
        servo_logger.logger.error(log_message)
        _ensure_playback_running()
        return {"error": "Impossible de demarrer la lecture"}, 500

    category_label = requested_category or _get_session_category(session_name)
    payload = {
        "status": "playing",
        "session": session_name,
        "category": category_label,
        "source": source,
    }
    return payload, 200


def _trigger_session_for_button(
    session_name: str, button_index: int, category: Optional[str]
) -> tuple[dict[str, Any], int]:
    source = f"esp32_button_{button_index}"
    payload, status = _enqueue_or_play_session(
        session_name,
        source,
        requested_category=category,
        log_context={"button": button_index, "requested_category": category},
    )
    payload.setdefault("button", button_index)
    payload.setdefault("category", category or _get_session_category(session_name))
    return payload, status


class ESP32Error(Exception):
    """Base class for ESP32 gateway errors."""


class ESP32ConfigError(ESP32Error):
    """Raised when ESP32 configuration is missing or disabled."""


class ESP32CommunicationError(ESP32Error):
    """Raised when ESP32 cannot be reached or returns invalid data."""


def _sanitize_esp32_endpoint(raw_host: str, raw_port: Any) -> Tuple[str, int]:
    host_value = (raw_host or "").strip()
    parsed_host = ""
    inferred_port: Optional[int] = None

    if host_value:
        to_parse = host_value
        if not to_parse.startswith(("http://", "https://")):
            to_parse = f"http://{to_parse}"
        parsed = urlparse(to_parse)
        parsed_host = parsed.hostname or ""
        if parsed.port:
            inferred_port = parsed.port
        if not parsed_host and host_value:
            parsed_host = host_value.split("/")[0]

    port_value = raw_port
    if port_value in (None, "", 0):
        port = inferred_port or 80
    else:
        try:
            port = int(port_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Port ESP32 invalide") from exc

    if port < 1 or port > 65535:
        raise ValueError("Le port ESP32 doit etre compris entre 1 et 65535")

    return parsed_host, port


def load_esp32_config() -> Dict[str, Any]:
    """Load ESP32 configuration (host, port, activation flag)."""
    config = dict(ESP32_DEFAULT_CONFIG)
    if not ESP32_CONFIG_PATH.exists():
        return config
    try:
        with open(ESP32_CONFIG_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception as exc:
        servo_logger.logger.warning("ESP32_CFG_LOAD_FAILED | %s", exc)
        return config

    if isinstance(raw, dict):
        host = raw.get("host")
        if isinstance(host, str):
            config["host"] = host.strip()

        port = raw.get("port")
        try:
            if port is not None:
                config["port"] = int(port)
        except (TypeError, ValueError):
            servo_logger.logger.warning("ESP32_CFG_LOAD_INVALID_PORT | %s", port)

        enabled = raw.get("enabled")
        if isinstance(enabled, bool):
            config["enabled"] = enabled
        elif enabled is not None:
            config["enabled"] = bool(enabled)

    return config


def update_esp32_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update and persist ESP32 configuration."""
    if not isinstance(payload, dict):
        raise ValueError("Format JSON invalide pour la configuration ESP32.")

    current = load_esp32_config()
    host_candidate = current["host"]
    if "host" in payload:
        host_candidate = str(payload.get("host") or "").strip()

    requested_port = payload.get("port", current["port"])

    try:
        sanitized_host, sanitized_port = _sanitize_esp32_endpoint(
            host_candidate, requested_port
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    enabled_candidate = payload.get("enabled", current["enabled"])
    if isinstance(enabled_candidate, bool):
        enabled_flag = enabled_candidate
    elif enabled_candidate is None:
        enabled_flag = False
    elif isinstance(enabled_candidate, str):
        enabled_flag = enabled_candidate.strip().lower() in {"1", "true", "yes", "on"}
    else:
        enabled_flag = bool(enabled_candidate)

    new_config = {
        "host": sanitized_host,
        "port": sanitized_port,
        "enabled": enabled_flag,
    }

    if new_config["enabled"] and not new_config["host"]:
        raise ValueError(
            "Configurer l'adresse IP ou le nom mDNS avant d'activer le pilotage ESP32."
        )

    _write_json_atomic(ESP32_CONFIG_PATH, new_config)
    return new_config


def _require_esp32_endpoint() -> Dict[str, Any]:
    config = load_esp32_config()
    if not config.get("enabled"):
        raise ESP32ConfigError("Pilotage ESP32 desactive.")

    host = config.get("host", "").strip()
    if not host:
        raise ESP32ConfigError("Aucune adresse ESP32 configuree.")

    port = config.get("port") or 80
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 80

    base = f"http://{host}"
    if port != 80:
        base = f"{base}:{port}"

    return {"base_url": base, "config": config}


def _esp32_request(
    path: str, method: str = "GET", json_payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    endpoint = _require_esp32_endpoint()
    base_url = endpoint["base_url"]
    url = f"{base_url}{path}"
    headers = {"Accept": "application/json"}
    data_bytes = None

    if json_payload is not None:
        data_bytes = json.dumps(json_payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data_bytes, headers=headers, method=method.upper())

    try:
        with urlopen(req, timeout=ESP32_HTTP_TIMEOUT) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read()
            if not raw:
                return {}
            text = raw.decode(charset, errors="replace")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ESP32CommunicationError(
                    "Reponse JSON invalide recue de l'ESP32."
                ) from exc
    except HTTPError as exc:
        body = ""
        try:
            raw_body = exc.read()
            if raw_body:
                body = raw_body.decode("utf-8", errors="replace")
        except Exception:
            body = ""
        servo_logger.logger.warning(
            "ESP32_HTTP_ERROR | method=%s | path=%s | status=%s | body=%s",
            method,
            path,
            exc.code,
            body[:200],
        )
        message = f"Erreur HTTP ESP32 ({exc.code})"
        if body:
            message = f"{message}: {body.strip()[:200]}"
        raise ESP32CommunicationError(message) from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        servo_logger.logger.warning(
            "ESP32_UNREACHABLE | method=%s | path=%s | reason=%s",
            method,
            path,
            reason,
        )
        raise ESP32CommunicationError(f"Connexion impossible ({reason})") from exc
    except ESP32ConfigError:
        raise
    except Exception as exc:
        servo_logger.logger.exception(
            "ESP32_UNEXPECTED_ERROR | method=%s | path=%s", method, path
        )
        raise ESP32CommunicationError(str(exc)) from exc


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


# -------------------- ESP32 Gateway --------------------


def _esp32_response_error(message: str, reason: str = "error") -> Dict[str, Any]:
    return {"reachable": False, "error": message, "reason": reason}


@app.route("/esp32/config", methods=["GET"])
def esp32_get_config():
    config = load_esp32_config()
    payload = dict(config)
    payload["buttonCount"] = ESP32_BUTTON_COUNT
    return jsonify(payload)


@app.route("/esp32/config", methods=["POST"])
def esp32_update_config():
    body = request.get_json(silent=True) or {}
    try:
        updated = update_esp32_config(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    payload = dict(updated)
    payload["buttonCount"] = ESP32_BUTTON_COUNT
    return jsonify(payload)


@app.route("/esp32/status")
def esp32_status():
    try:
        status_payload = _esp32_request("/api/status", method="GET")
        return jsonify({"reachable": True, "status": status_payload})
    except ESP32ConfigError as exc:
        return jsonify(_esp32_response_error(str(exc), reason="config"))
    except ESP32CommunicationError as exc:
        return jsonify(_esp32_response_error(str(exc), reason="network"))


@app.route("/esp32/relay", methods=["POST"])
def esp32_set_relay():
    body = request.get_json(silent=True) or {}
    if "on" not in body:
        return jsonify({"success": False, "error": "Champ 'on' manquant."}), 400
    desired = bool(body.get("on"))
    try:
        payload = _esp32_request(
            "/api/relay", method="POST", json_payload={"on": desired}
        )
        return jsonify({"success": True, "reachable": True, "response": payload})
    except ESP32ConfigError as exc:
        return jsonify({"success": False, "reachable": False, "error": str(exc)})
    except ESP32CommunicationError as exc:
        return jsonify({"success": False, "reachable": False, "error": str(exc)})


@app.route("/esp32/auto-relay", methods=["POST"])
def esp32_set_auto_relay():
    body = request.get_json(silent=True) or {}
    if "enabled" not in body:
        return jsonify({"success": False, "error": "Champ 'enabled' manquant."}), 400
    enabled = bool(body.get("enabled"))
    try:
        payload = _esp32_request(
            "/api/auto-relay", method="POST", json_payload={"enabled": enabled}
        )
        return jsonify({"success": True, "reachable": True, "response": payload})
    except ESP32ConfigError as exc:
        return jsonify({"success": False, "reachable": False, "error": str(exc)})
    except ESP32CommunicationError as exc:
        return jsonify({"success": False, "reachable": False, "error": str(exc)})


@app.route("/esp32/button-config", methods=["GET"])
def esp32_button_config():
    assignments = _load_button_assignments()
    try:
        payload = _esp32_request("/api/button-config", method="GET")
        states = payload.get("states")
        if not isinstance(states, list):
            states = payload.get("buttons")
        response: Dict[str, Any] = {
            "reachable": True,
            "buttonCount": ESP32_BUTTON_COUNT,
            "assignments": assignments,
        }
        response["sessions"] = assignments
        response["categories"] = _load_session_categories()["categories"]
        if isinstance(states, list):
            response["states"] = states
        return jsonify(response)
    except ESP32ConfigError as exc:
        error = _esp32_response_error(str(exc), reason="config")
        error["assignments"] = assignments
        error["buttonCount"] = ESP32_BUTTON_COUNT
        error["sessions"] = assignments
        error["categories"] = _load_session_categories()["categories"]
        return jsonify(error)
    except ESP32CommunicationError as exc:
        error = _esp32_response_error(str(exc), reason="network")
        error["assignments"] = assignments
        error["buttonCount"] = ESP32_BUTTON_COUNT
        error["sessions"] = assignments
        error["categories"] = _load_session_categories()["categories"]
        return jsonify(error)


@app.route("/esp32/button-config", methods=["POST"])
def esp32_set_button_config():
    body = request.get_json(silent=True) or {}
    if "button" not in body:
        return jsonify({"success": False, "error": "Champ 'button' manquant."}), 400

    try:
        button_index = int(body.get("button"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Index de bouton invalide."}), 400

    if button_index < 0 or button_index >= ESP32_BUTTON_COUNT:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Index bouton hors limites (0-{ESP32_BUTTON_COUNT - 1}).",
                }
            ),
            400,
        )

    raw_category = body.get("category")
    if raw_category is None:
        raw_category = body.get("session", "")
    if raw_category is None:
        raw_category = ""
    if not isinstance(raw_category, str):
        raw_category = str(raw_category)
    category = raw_category.strip()

    try:
        updated_assignments = _set_button_assignment(button_index, category)
    except IndexError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    servo_logger.logger.info(
        "ESP32_BUTTON_CATEGORY_SET | button=%s | category=%s",
        button_index,
        category or "-",
    )

    reachable = False
    remote_error: Optional[str] = None
    remote_response: Dict[str, Any] = {}
    try:
        remote_response = _esp32_request(
            "/api/button-config",
            method="POST",
            json_payload={
                "button": button_index,
                "category": category,
                "session": category,
            },
        )
    except ESP32ConfigError as exc:
        remote_error = str(exc)
    except ESP32CommunicationError as exc:
        remote_error = str(exc)
    else:
        reachable = True

    response_payload: Dict[str, Any] = {
        "success": True,
        "reachable": reachable,
        "assignments": updated_assignments,
        "button": button_index,
        "category": category,
        "categories": _load_session_categories()["categories"],
    }
    if remote_response:
        response_payload["response"] = remote_response
    if remote_error:
        response_payload["error"] = remote_error
    return jsonify(response_payload)


@app.route("/esp32/button/<int:button_index>/play", methods=["POST"])
def esp32_button_play(button_index: int):
    if button_index < 0 or button_index >= ESP32_BUTTON_COUNT:
        return (
            jsonify(
                {
                    "error": f"Index bouton hors limites (0-{ESP32_BUTTON_COUNT - 1})."
                }
            ),
            400,
        )

    try:
        status_info = player.status()
    except Exception:
        status_info = {}

    running = bool(status_info.get("running"))
    has_queue = playlist.has_items()
    has_current = _get_current_entry() is not None
    if running or has_queue or has_current:
        return (
            jsonify(
                {
                    "error": "Lecture en cours. Attendre la fin avant de relancer via l'ESP32.",
                    "status": "busy",
                    "running": running,
                    "queue_size": playlist.size(),
                }
            ),
            409,
        )

    assignments = _load_button_assignments()
    try:
        category = assignments[button_index]
    except IndexError:
        category = ""
    category = (category or "").strip()
    if not category:
        return jsonify({"error": "Ce bouton n'est pas associe a une categorie."}), 400

    sessions = _sessions_for_category(category)
    if not sessions:
        return jsonify(
            {
                "error": f"Aucune session disponible pour la categorie '{category}'.",
                "category": category,
            }
        ), 404

    chosen_session = random.choice(sessions)
    payload, status_code = _trigger_session_for_button(
        chosen_session, button_index, category
    )
    payload["category"] = category
    payload["session"] = chosen_session
    payload["button"] = button_index
    payload["available_sessions"] = sessions
    return jsonify(payload), status_code


@app.route("/esp32/restart", methods=["POST"])
def esp32_restart():
    try:
        payload = _esp32_request("/api/restart", method="POST", json_payload={})
        return jsonify({"success": True, "reachable": True, "response": payload})
    except ESP32ConfigError as exc:
        return jsonify({"success": False, "reachable": False, "error": str(exc)})
    except ESP32CommunicationError as exc:
        return jsonify({"success": False, "reachable": False, "error": str(exc)})


def sanitize_scene_name(name: str) -> str:
    """Nettoie le nom de scène pour créer un nom de répertoire valide"""
    if not name or not name.strip():
        raise ValueError("Nom de scène requis")

    # Supprimer espaces et caractères spéciaux, garder uniquement alphanum + _ -
    name = name.strip()
    sanitized = re.sub(r"[^a-zA-Z0-9 _-]", "", name)
    sanitized = sanitized.strip()

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

        json_path = session_dir / json_filename
        mp3_path = session_dir / mp3_filename

        json_file.save(json_path)
        mp3_file.save(mp3_path)

        cache_file = mp3_path.with_name(f"{mp3_path.stem}.cached.wav")
        tmp_cache = cache_file.with_name(cache_file.name + ".tmp")
        try:
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(str(tmp_cache), format="wav")
            tmp_cache.replace(cache_file)
            servo_logger.logger.info(
                "UPLOAD_CACHE_CREATED | session=%s | cache=%s",
                clean_name,
                cache_file.name,
            )
        except Exception as cache_exc:
            servo_logger.logger.warning(
                "UPLOAD_CACHE_FAILED | session=%s | cache=%s | error=%s",
                clean_name,
                cache_file.name,
                cache_exc,
            )
            try:
                if tmp_cache.exists():
                    tmp_cache.unlink()
            except Exception:
                pass

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
        sessions_list = _list_session_names()
        categories_data = _load_session_categories()
        mapping = categories_data["sessions"]
        response_sessions = []
        for name in sessions_list:
            response_sessions.append({"name": name, "category": mapping.get(name)})
        return jsonify(
            {
                "sessions": response_sessions,
                "categories": categories_data["categories"],
            }
        )
    except Exception as e:
        return jsonify({"error": f"Erreur lors du listage: {str(e)}"}), 500


@app.route("/api/sessions", methods=["GET"])
def api_sessions():
    categories_data = _load_session_categories()
    mapping = categories_data["sessions"]

    current_raw = _get_current_entry()
    queue_raw = playlist.snapshot()
    enriched_current = _enrich_entry_with_category(current_raw, mapping)
    enriched_queue = _enrich_queue_with_categories(queue_raw, mapping)

    playlist_snapshot = {
        "current": enriched_current,
        "queue": enriched_queue,
    }

    original_queue_length = len(enriched_queue)
    now = time.time()
    with _transition_state_lock:
        last_finish_ts = _last_finish_ts
        last_finish_reason = _last_finish_reason

    hold_active = (
        enriched_current is None
        and enriched_queue
        and last_finish_reason in _TRANSITION_HOLD_REASONS
        and last_finish_ts > 0.0
        and (now - last_finish_ts) <= TRANSITION_HOLD_SECONDS
    )

    if hold_active:
        placeholder_entry = enriched_queue[0].copy()
        placeholder_entry["pending"] = True
        placeholder_entry["transitioning"] = True
        placeholder_entry["transition_reason"] = last_finish_reason
        placeholder_entry["transition_started_at"] = last_finish_ts
        playlist_snapshot["current"] = placeholder_entry
        playlist_snapshot["queue"] = enriched_queue[1:]
    else:
        playlist_snapshot["queue"] = enriched_queue

    meta = _client_request_metadata()
    current_entry = playlist_snapshot["current"]
    current_session = (
        current_entry.get("session")
        if isinstance(current_entry, dict)
        else None
    )
    queue_length = original_queue_length
    transition_state = "pending" if hold_active else "steady"
    servo_logger.logger.info(
        "ESP32_STATUS_POLL | remote=%s | forwarded=%s | ua=%s | current=%s | queue_len=%s | transition=%s",
        meta["client_ip"],
        meta["forwarded_for"],
        meta["user_agent"],
        current_session or "-",
        queue_length,
        transition_state,
    )
    return jsonify(
        {
            "playlist": playlist_snapshot,
            "categories": categories_data["categories"],
        }
    )


@app.route("/sessions/<session_name>/category", methods=["PUT"])
def set_session_category(session_name: str):
    try:
        _ensure_session_exists(session_name)
    except ValueError:
        return jsonify({"error": "Session introuvable"}), 404

    payload = request.get_json(silent=True) or {}
    category = payload.get("category")
    try:
        updated = _set_session_category(session_name, category)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "session": session_name,
            "category": updated["sessions"].get(session_name),
            "categories": updated["categories"],
        }
    )


@app.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "GET":
        data = _load_session_categories()
        return jsonify({"categories": data["categories"]})

    payload = request.get_json(silent=True) or {}
    category_name = payload.get("name")
    sanitized_name = (category_name or "").strip()
    try:
        updated, created = _add_category(sanitized_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    stored_name = sanitized_name
    if created:
        stored_name = updated["categories"][-1]
    elif sanitized_name:
        for existing in updated["categories"]:
            if existing == sanitized_name:
                stored_name = existing
                break
    return (
        jsonify({"category": stored_name, "categories": updated["categories"]}),
        201 if created else 200,
    )


@app.route("/sessions/<session_name>", methods=["DELETE"])
def delete_session(session_name: str):
    """Supprime complètement une session et son répertoire."""
    try:
        session_dir = _resolve_existing_session_dir(session_name)
    except FileNotFoundError:
        return jsonify({"error": "Session introuvable"}), 404
    except ValueError:
        return jsonify({"error": "Nom de session invalide"}), 400

    removed_items = playlist.purge_session(session_dir.name)
    removed_count = len(removed_items)

    current = _get_current_entry()
    stop_triggered = False
    if current and current.get("session") == session_dir.name:
        servo_logger.logger.info("SESSION_DELETE_STOP | session=%s", session_dir.name)
        try:
            status_info = player.status()
        except Exception:
            status_info = {}
        try:
            player.stop(reason="skip")
            stop_triggered = bool(status_info.get("running"))
        except Exception:
            servo_logger.logger.exception(
                "SESSION_DELETE_STOP_FAILED | session=%s", session_dir.name
            )
        finally:
            _set_current_entry(None)

    try:
        shutil.rmtree(session_dir)
    except FileNotFoundError:
        return jsonify({"error": "Session introuvable"}), 404
    except Exception as exc:
        servo_logger.logger.exception(
            "SESSION_DELETE_FAILED | session=%s | error=%s", session_dir.name, exc
        )
        return (
            jsonify({"error": f"Impossible de supprimer la session: {exc}"}),
            500,
        )

    servo_logger.logger.info(
        "SESSION_DELETED | session=%s | removed_from_queue=%s | stopped=%s",
        session_dir.name,
        removed_count,
        stop_triggered,
    )

    try:
        _set_session_category(session_dir.name, None)
    except Exception:
        servo_logger.logger.exception(
            "SESSION_CATEGORY_REMOVE_FAILED | session=%s", session_dir.name
        )

    try:
        _ensure_playback_running()
    except Exception:
        servo_logger.logger.exception(
            "SESSION_DELETE_AUTOSTART_FAILED | session=%s", session_dir.name
        )

    return jsonify(
        {
            "status": "deleted",
            "session": session_dir.name,
            "removed_from_queue": removed_count,
            "stopped": stop_triggered,
        }
    )


@app.route("/play", methods=["POST"])
def play():
    try:
        body = request.get_json(silent=True) or {}
        requested_value = body.get("session")
        if not requested_value:
            return jsonify({"error": "Champ 'session' manquant"}), 400

        try:
            initial_session, requested_category = _resolve_session_candidate(
                requested_value
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        random_mode_enabled = _is_random_mode_enabled()
        random_choice = None
        random_applied = False
        selected_session = initial_session

        if random_mode_enabled:
            random_choice = _pick_random_session([initial_session])
            if random_choice:
                selected_session = random_choice
                random_applied = selected_session != initial_session
                if random_applied:
                    _record_random_pick(selected_session, initial_session)
                    servo_logger.logger.info(
                        "RANDOM_MODE_SELECT | requested=%s | selected=%s",
                        requested_value,
                        selected_session,
                    )
            else:
                servo_logger.logger.warning(
                    "RANDOM_MODE_NO_ELIGIBLE | requested=%s", requested_value
                )

        category_hint = None if random_applied else requested_category
        payload, status_code = _enqueue_or_play_session(
            selected_session,
            "manual",
            requested_category=category_hint,
            log_context={
                "requested": requested_value,
                "requested_category": requested_category,
                "random_mode": random_mode_enabled,
            },
        )

        if status_code >= 400:
            return jsonify(payload), status_code

        payload["random_mode"] = {
            "enabled": random_mode_enabled,
            "applied": random_applied,
            "requested": requested_value,
            "selected": selected_session,
            "available": random_choice is not None,
        }
        return jsonify(payload), status_code
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Impossible de demarrer la lecture: {e}"}), 400


@app.route("/api/enqueue", methods=["POST"])
def api_enqueue():
    body = request.get_json(silent=True) or {}
    meta = _client_request_metadata()
    body_log = _format_log_payload(body)
    servo_logger.logger.info(
        "ESP32_ENQUEUE_REQUEST | remote=%s | forwarded=%s | ua=%s | body=%s",
        meta["client_ip"],
        meta["forwarded_for"],
        meta["user_agent"],
        body_log,
    )

    requested_value = body.get("session")
    if not requested_value:
        servo_logger.logger.warning(
            "ESP32_ENQUEUE_REJECTED | remote=%s | reason=missing_session | body=%s",
            meta["client_ip"],
            body_log,
        )
        return jsonify({"success": False, "error": "Champ 'session' manquant"}), 400

    try:
        session_name, requested_category = _resolve_session_candidate(requested_value)
    except ValueError as exc:
        servo_logger.logger.warning(
            "ESP32_ENQUEUE_REJECTED | remote=%s | reason=invalid_session | error=%s | body=%s",
            meta["client_ip"],
            exc,
            body_log,
        )
        return jsonify({"success": False, "error": str(exc)}), 400

    payload, status_code = _enqueue_or_play_session(
        session_name,
        "esp32_api",
        requested_category=requested_category,
        log_context={"requested": requested_value},
    )

    response_log = _format_log_payload(payload)
    if status_code >= 400:
        payload["success"] = False
        logger_fn = servo_logger.logger.error if status_code >= 500 else servo_logger.logger.warning
        logger_fn(
            "ESP32_ENQUEUE_RESPONSE | remote=%s | status=%s | session=%s | error=%s | payload=%s",
            meta["client_ip"],
            status_code,
            payload.get("session") or session_name,
            payload.get("error") or "-",
            response_log,
        )
        return jsonify(payload), status_code

    payload["success"] = True
    payload["requested"] = requested_value
    servo_logger.logger.info(
        "ESP32_ENQUEUE_RESPONSE | remote=%s | status=%s | session=%s | state=%s | payload=%s",
        meta["client_ip"],
        status_code,
        payload.get("session") or session_name,
        payload.get("status") or "-",
        response_log,
    )
    return jsonify(payload), status_code


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
        st["current_playlist"] = _enrich_entry_with_category(_get_current_entry())
        random_snapshot = _random_mode_snapshot()
        random_snapshot["eligible_count"] = len(_eligible_random_sessions())
        random_snapshot["excluded"] = sorted(_RANDOM_EXCLUDED_NAMES)
        random_snapshot["available"] = random_snapshot["eligible_count"] > 0
        st["random_mode"] = random_snapshot
        if BT_DEVICE_ADDR:
            info = _bluetooth_info(BT_DEVICE_ADDR)
            volume_percent: int | None = None
            if info and info.get("connected") is True:
                try:
                    transport, _ = _pick_transport_path()
                    if transport:
                        current, _ = _get_transport_volume(transport)
                        if isinstance(current, (int, float)):
                            volume_percent = int(round(current))
                except FileNotFoundError:
                    volume_percent = None
                except subprocess.TimeoutExpired:
                    volume_percent = None
                except Exception:  # pragma: no cover - defensive logging
                    servo_logger.logger.exception("STATUS_VOLUME_READ_ERROR")
                    volume_percent = None
            st["bluetooth"] = {
                "address": BT_DEVICE_ADDR,
                "connected": info.get("connected") if info else None,
            }
            if volume_percent is not None:
                st["bluetooth"]["volume_percent"] = volume_percent
        return jsonify(st)
    except Exception as e:
        return jsonify({"error": f"Erreur status: {e}"}), 500


@app.route("/random_mode", methods=["GET", "POST"])
def random_mode():
    if request.method == "GET":
        snapshot = _random_mode_snapshot()
        eligible = _eligible_random_sessions()
        snapshot["eligible"] = eligible
        snapshot["eligible_count"] = len(eligible)
        snapshot["excluded"] = sorted(_RANDOM_EXCLUDED_NAMES)
        snapshot["available"] = bool(eligible)
        return jsonify(snapshot)

    payload = request.get_json(silent=True) or {}
    if "enabled" not in payload:
        return jsonify({"error": "Champ 'enabled' manquant"}), 400

    enabled_value = payload.get("enabled")
    if not isinstance(enabled_value, bool):
        return jsonify({"error": "Le champ 'enabled' doit etre booleen"}), 400

    changed = _set_random_mode_enabled(enabled_value)
    if changed:
        servo_logger.logger.info("RANDOM_MODE_TOGGLE | enabled=%s", enabled_value)

    snapshot = _random_mode_snapshot()
    eligible = _eligible_random_sessions()
    snapshot["eligible"] = eligible
    snapshot["eligible_count"] = len(eligible)
    snapshot["excluded"] = sorted(_RANDOM_EXCLUDED_NAMES)
    snapshot["changed"] = changed
    snapshot["available"] = bool(eligible)
    return jsonify(snapshot)


@app.route("/volume", methods=["POST"])
def volume():
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").lower()
    if action not in VOLUME_ACTIONS:
        return jsonify({"error": "Unknown volume action"}), 400

    target_value: int | None = None
    if action == "set":
        if "value" not in payload:
            return jsonify({"error": "Valeur volume manquante"}), 400
        try:
            target_value = int(float(payload.get("value")))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return jsonify({"error": "Valeur volume invalide"}), 400
        target_value = max(0, min(VOLUME_MAX, target_value))

    ok, message, applied = _run_volume_action(action, target_value)
    response = {"action": action, "ok": ok}
    if message:
        response["message"] = message
    if applied is not None:
        response["volume"] = int(applied)
    status = 200 if ok else 500
    return jsonify(response), status


@app.route("/playlist", methods=["GET", "POST"])
def playlist_api():
    try:
        if request.method == "GET":
            categories_data = _load_session_categories()
            mapping = categories_data["sessions"]
            return jsonify(
                {
                    "current": _enrich_entry_with_category(
                        _get_current_entry(), mapping
                    ),
                    "queue": _enrich_queue_with_categories(
                        playlist.snapshot(), mapping
                    ),
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
        enriched_current = _enrich_entry_with_category(current)
        if enriched_current and enriched_current.get("id") == item["id"]:
            status = "playing"
            http_code = 200

        enriched_item = _enrich_entry_with_category(item)
        return (
            jsonify(
                {
                    "status": status,
                    "item": enriched_item,
                    "position": position,
                    "current": enriched_current,
                }
            ),
            http_code,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erreur playlist: {e}"}), 500


@app.route("/playlist/shuffle", methods=["POST"])
def playlist_shuffle():
    sessions = _eligible_random_sessions()
    if not sessions:
        return (
            jsonify({"error": "Aucune session disponible pour la lecture aléatoire"}),
            400,
        )

    random.shuffle(sessions)

    try:
        player.stop(reason="shuffle")
    except Exception:
        servo_logger.logger.exception("PLAYLIST_SHUFFLE_STOP_FAILED")

    _set_current_entry(None)
    playlist.clear()

    for session_name in sessions:
        playlist.add(session_name)

    servo_logger.logger.info(
        "PLAYLIST_SHUFFLE | count=%s | sessions=%s", len(sessions), ", ".join(sessions)
    )

    _ensure_playback_running()

    categories_data = _load_session_categories()
    mapping = categories_data["sessions"]
    return jsonify(
        {
            "status": "shuffled",
            "count": len(sessions),
            "sessions": sessions,
            "playlist": _enrich_queue_with_categories(
                playlist.snapshot(), mapping
            ),
        }
    )


@app.route("/playlist/<int:item_id>", methods=["DELETE"])
def playlist_delete(item_id: int):
    removed = playlist.remove(item_id)
    if not removed:
        return jsonify({"error": "Element introuvable"}), 404
    servo_logger.logger.info(
        f"PLAYLIST_REMOVE | id={item_id} | session={removed['session']}"
    )
    enriched = _enrich_entry_with_category(removed)
    return jsonify({"status": "removed", "item": enriched})


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
            return jsonify(
                {
                    "status": "playing",
                    "current": _enrich_entry_with_category(current),
                }
            )
        return jsonify({"status": "idle"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erreur skip: {e}"}), 500


@app.route("/service/restart", methods=["POST"])
def service_restart():
    """Restart the servo-sync systemd service from the web UI."""
    if not SERVICE_RESTART_CMD:
        return jsonify({"error": "Commande restart non configurée"}), 500

    try:
        servo_logger.logger.info(
            "SERVICE_RESTART_REQUEST | cmd=%s", SERVICE_RESTART_CMD[0]
        )
        proc = subprocess.run(
            SERVICE_RESTART_CMD,
            check=False,
            capture_output=True,
            text=True,
            timeout=SERVICE_RESTART_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        servo_logger.logger.error(
            "SERVICE_RESTART_TIMEOUT | timeout=%s", SERVICE_RESTART_TIMEOUT
        )
        return jsonify({"error": "Redémarrage service timeout"}), 504
    except Exception:
        servo_logger.logger.exception("SERVICE_RESTART_ERROR")
        return jsonify({"error": "Redémarrage service impossible"}), 500

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        servo_logger.logger.error(
            "SERVICE_RESTART_FAILED | code=%s | stderr=%s",
            proc.returncode,
            stderr[:400],
        )
        return (
            jsonify(
                {
                    "error": "Échec redémarrage service",
                    "code": proc.returncode,
                    "stderr": stderr,
                }
            ),
            500,
        )

    if stdout:
        servo_logger.logger.info("SERVICE_RESTART_STDOUT | %s", stdout[:400])
    if stderr:
        servo_logger.logger.info("SERVICE_RESTART_STDERR | %s", stderr[:400])

    return jsonify({"status": "restarted"})


@app.route("/bluetooth/restart", methods=["POST"])
def bluetooth_restart():
    """Restart the bluetooth systemd service from the web UI."""
    if not BLUETOOTH_RESTART_CMD:
        return jsonify({"error": "Commande restart Bluetooth non configurée"}), 500

    try:
        servo_logger.logger.info(
            "BLUETOOTH_RESTART_REQUEST | cmd=%s", BLUETOOTH_RESTART_CMD[0]
        )
        proc = subprocess.run(
            BLUETOOTH_RESTART_CMD,
            check=False,
            capture_output=True,
            text=True,
            timeout=BLUETOOTH_RESTART_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        servo_logger.logger.error(
            "BLUETOOTH_RESTART_TIMEOUT | timeout=%s", BLUETOOTH_RESTART_TIMEOUT
        )
        return jsonify({"error": "Redémarrage Bluetooth timeout"}), 504
    except Exception:
        servo_logger.logger.exception("BLUETOOTH_RESTART_ERROR")
        return jsonify({"error": "Redémarrage Bluetooth impossible"}), 500

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        servo_logger.logger.error(
            "BLUETOOTH_RESTART_FAILED | code=%s | stderr=%s",
            proc.returncode,
            stderr[:400],
        )
        return (
            jsonify(
                {
                    "error": "Échec redémarrage Bluetooth",
                    "code": proc.returncode,
                    "stderr": stderr,
                }
            ),
            500,
        )

    if stdout:
        servo_logger.logger.info("BLUETOOTH_RESTART_STDOUT | %s", stdout[:400])
    if stderr:
        servo_logger.logger.info("BLUETOOTH_RESTART_STDERR | %s", stderr[:400])

    return jsonify({"status": "restarted"})


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
