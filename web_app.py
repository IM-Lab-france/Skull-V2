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
import atexit
import signal
from functools import wraps
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
from logger import servo_logger
from runtime_factory import resolve_runtime_mode
from runtime_lock import RuntimeProcessLock
from api.legacy import create_legacy_blueprint
from api.bluetooth import BluetoothUiContext, create_bluetooth_blueprint
from api.v1 import V1Context, create_v1_blueprint
from domain.errors import DependencyUnavailableError, InvalidInputError, OperationNotAllowedError
from domain.bluetooth import (
    has_audio_sink_profile,
    parse_bluez_uuids,
    validate_bluetooth_address,
)
from domain.playlist import PlaybackStateStore, PlaylistStore, RandomSessionSelector
from domain.session_catalog import SessionCatalog
from services import LegacyPlaybackService
from services.bluetooth_commands import BluetoothCommandRunner
from services.bluetooth_reconnect import (
    BluetoothReconnectController,
    BluetoothReconnectWorker,
    ReconnectResult,
)
from services.esp32_supervisor import ESP32ProbeSnapshot, ESP32Supervisor
from adapters_runtime import PulseAudioOutputAdapter

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(exist_ok=True)
PITCH_CONFIG_PATH = CONFIG_DIR / "pitch_offsets.json"
CHANNELS_CONFIG_PATH = CONFIG_DIR / "channels_state.json"
ESP32_CONFIG_PATH = CONFIG_DIR / "esp32_settings.json"
SESSION_CATEGORIES_PATH = CONFIG_DIR / "session_categories.json"
ESP32_BUTTON_ASSIGNMENTS_PATH = CONFIG_DIR / "esp32_button_categories.json"
LOOP_AUDIO_DIR = CONFIG_DIR / "loop_audio"
APP_VERSION = os.environ.get("SKULL_APP_VERSION", "dev")
LOG_STREAM_WINDOW_SECONDS = max(
    0.1, min(5.0, float(os.environ.get("SKULL_LOG_STREAM_WINDOW_SECONDS", "0.5")))
)
LOG_STREAM_POLL_INTERVAL = max(
    0.05, min(1.0, float(os.environ.get("SKULL_LOG_STREAM_POLL_INTERVAL", "0.1")))
)

ACCUEIL_WEBHOOK_URL = (
    os.environ.get(
        "PLAYLIST_ACCUEIL_WEBHOOK",
        os.environ.get("SKULL_SMOKE_WEBHOOK_URL", ""),
    ).strip()
    or ""
)
ACCUEIL_WEBHOOK_TIMEOUT = float(
    os.environ.get("PLAYLIST_ACCUEIL_WEBHOOK_TIMEOUT", "2.0")
)

app = Flask(__name__, static_folder="static", template_folder="templates")
legacy_api = create_legacy_blueprint()


class _LazyRuntimeComponent:
    """Compatibility proxy that creates hardware only during explicit startup."""

    def __init__(self, component_name: str) -> None:
        object.__setattr__(self, "_component_name", component_name)

    def _resolve(self):
        return _runtime_component(self._component_name)

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)

    def __setattr__(self, name: str, value) -> None:
        if name == "_component_name":
            object.__setattr__(self, name, value)
            return
        setattr(self._resolve(), name, value)


_runtime_state_lock = threading.RLock()
_runtime_player = None
_runtime_loop_player = None
_runtime_process_lock: Optional[RuntimeProcessLock] = None
_runtime_initialized = False
_runtime_cleaned = False

player = _LazyRuntimeComponent("player")
loop_player = _LazyRuntimeComponent("loop_player")


def _runtime_component(name: str):
    """Return one initialized runtime component through the compatibility proxy."""
    initialize_runtime()
    component = _runtime_player if name == "player" else _runtime_loop_player
    if component is None:  # pragma: no cover - defensive invariant
        raise RuntimeError("Skull runtime component is not initialized")
    return component


def _default_runtime_lock() -> RuntimeProcessLock:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    lock_path = os.environ.get(
        "SKULL_RUNTIME_LOCK_PATH",
        str(Path(runtime_dir) / "skull-runtime.lock"),
    )
    timeout = float(os.environ.get("SKULL_RUNTIME_LOCK_TIMEOUT", "2.0"))
    return RuntimeProcessLock(lock_path, timeout=timeout)


def initialize_runtime(
    *,
    acquire_process_lock: bool = False,
    sync_player_cls=None,
    loop_player_cls=None,
    process_lock=None,
):
    """Validate configuration and initialize both runtime components once."""
    global _runtime_player, _runtime_loop_player
    global _runtime_process_lock, _runtime_initialized, _runtime_cleaned

    with _runtime_state_lock:
        if _runtime_initialized:
            return _runtime_player, _runtime_loop_player
        if _runtime_cleaned:
            raise RuntimeError("Skull runtime was already cleaned up")

        # Validate the mode before importing or constructing hardware modules.
        selected_mode = resolve_runtime_mode()
        if sync_player_cls is None or loop_player_cls is None:
            from sync_player import SyncPlayer
            from loop_player import LoopPlayer

            sync_player_cls = sync_player_cls or SyncPlayer
            loop_player_cls = loop_player_cls or LoopPlayer

        acquired_lock = None
        created_player = None
        created_loop_player = None
        try:
            if acquire_process_lock and selected_mode == "production":
                acquired_lock = process_lock or _default_runtime_lock()
                acquired_lock.acquire()

            created_player = sync_player_cls()
            created_loop_player = loop_player_cls(LOOP_AUDIO_DIR)
            setattr(created_player, "channels", player_channels)
            created_player.set_on_track_finished(_handle_track_finished)

            _runtime_player = created_player
            _runtime_loop_player = created_loop_player
            _runtime_process_lock = acquired_lock
            _runtime_initialized = True
            if BT_DEVICE_ADDR and selected_mode == "production":
                # The first BlueZ read also belongs to the worker so the
                # Gunicorn startup hook never waits on Bluetooth.
                _start_bt_reconnect_worker(BT_DEVICE_ADDR)
            if selected_mode == "production" and load_esp32_config().get("enabled"):
                _start_esp32_supervisor()
            return _runtime_player, _runtime_loop_player
        except Exception:
            _cleanup_component(created_loop_player, prefer_cleanup=False)
            _cleanup_component(created_player, prefer_cleanup=True)
            if acquired_lock is not None:
                acquired_lock.release()
            raise


def _cleanup_component(component, *, prefer_cleanup: bool) -> None:
    if component is None:
        return
    method_name = "cleanup" if prefer_cleanup else "stop"
    method = getattr(component, method_name, None)
    if callable(method):
        try:
            method()
        except Exception:
            try:
                servo_logger.logger.exception("RUNTIME_CLEANUP_FAILED")
            except Exception:
                pass


def _legacy_playback_service() -> LegacyPlaybackService:
    """Build the compatibility service from the current runtime components."""
    return LegacyPlaybackService(audio=player, loop=loop_player)


def cleanup_runtime() -> None:
    """Stop runtime resources once and release the cross-process lock."""
    global _runtime_process_lock, _runtime_cleaned

    _bt_reconnect_cancel.set()
    if _bt_reconnect_controller is not None:
        _bt_reconnect_controller.cancel()
    if _bt_reconnect_worker is not None:
        stop_worker = getattr(_bt_reconnect_worker, "stop", None)
        if callable(stop_worker):
            stop_worker(timeout=1.0)
    if _esp32_supervisor is not None:
        stop_supervisor = getattr(_esp32_supervisor, "stop", None)
        if callable(stop_supervisor):
            stop_supervisor(timeout=1.0)

    with _runtime_state_lock:
        if _runtime_cleaned:
            return
        _runtime_cleaned = True
        current_player = _runtime_player
        current_loop_player = _runtime_loop_player
        current_lock = _runtime_process_lock

        try:
            _cleanup_component(current_loop_player, prefer_cleanup=False)
        finally:
            try:
                _cleanup_component(current_player, prefer_cleanup=True)
            finally:
                if current_lock is not None:
                    current_lock.release()
                    _runtime_process_lock = None


atexit.register(cleanup_runtime)


def _install_shutdown_handlers() -> None:
    def _handle_shutdown(signum, _frame) -> None:
        cleanup_runtime()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)


def _health_mode() -> tuple[Optional[str], bool]:
    """Return a public mode label and whether the configuration is valid."""
    try:
        selected = resolve_runtime_mode()
    except Exception:
        return None, False
    return ("simulated" if selected == "simulated" else "real"), True


def _health_snapshot(*, live: bool) -> tuple[dict[str, object], int]:
    mode, config_ok = _health_mode()
    checks: dict[str, bool] = {"configuration": config_ok}
    if live:
        checks["process"] = True
        return {
            "status": "ok",
            "version": APP_VERSION,
            "mode": mode,
            "checks": checks,
        }, 200

    runtime_ok = (
        _runtime_initialized
        and _runtime_player is not None
        and _runtime_loop_player is not None
    )
    checks.update(
        {
            "runtime_initialized": _runtime_initialized,
            "player": _runtime_player is not None,
            "loop_player": _runtime_loop_player is not None,
        }
    )
    ready = config_ok and runtime_ok
    return {
        "status": "ready" if ready else "not_ready",
        "version": APP_VERSION,
        "mode": mode,
        "checks": checks,
    }, (200 if ready else 503)


@legacy_api.route("/health/live", methods=["GET"])
def health_live():
    """Report that HTTP is alive without touching runtime components."""
    snapshot, status_code = _health_snapshot(live=True)
    return jsonify(snapshot), status_code


@legacy_api.route("/health/ready", methods=["GET"])
def health_ready():
    """Report readiness only after configuration and runtime initialization."""
    snapshot, status_code = _health_snapshot(live=False)
    return jsonify(snapshot), status_code

VOLUME_TIMEOUT = float(os.environ.get("PLAYLIST_VOLUME_TIMEOUT", "5"))
VOLUME_STEP = int(os.environ.get("PLAYLIST_VOLUME_STEP", "8"))
VOLUME_MAX = int(os.environ.get("PLAYLIST_VOLUME_MAX", "127"))
VOLUME_TOOL = os.environ.get("PLAYLIST_VOLUME_CLI", "bluetoothctl")
_VOLUME_CMD_BASE = shlex.split(VOLUME_TOOL) if VOLUME_TOOL else ["bluetoothctl"]
if not _VOLUME_CMD_BASE:
    _VOLUME_CMD_BASE = ["bluetoothctl"]
_BLUETOOTH_COMMAND_RUNNER = BluetoothCommandRunner(
    _VOLUME_CMD_BASE, timeout=VOLUME_TIMEOUT
)
BT_CONNECT_COMMAND_TIMEOUT = max(
    5.0, float(os.environ.get("PLAYLIST_BT_CONNECT_COMMAND_TIMEOUT", "20"))
)

PULSE_AUDIO_TIMEOUT = float(os.environ.get("PLAYLIST_PULSE_AUDIO_TIMEOUT", "5"))
PULSE_AUDIO_WAIT_TIMEOUT = max(
    0.1, float(os.environ.get("PLAYLIST_PULSE_AUDIO_WAIT_TIMEOUT", "5"))
)
PULSE_AUDIO_POLL_INTERVAL = max(
    0.05, float(os.environ.get("PLAYLIST_PULSE_AUDIO_POLL_INTERVAL", "0.2"))
)
PULSE_AUDIO_TOOL = os.environ.get("PLAYLIST_PULSE_AUDIO_CLI", "pactl")
_PULSE_AUDIO_CMD_BASE = (
    shlex.split(PULSE_AUDIO_TOOL) if PULSE_AUDIO_TOOL else ["pactl"]
)
if not _PULSE_AUDIO_CMD_BASE:
    _PULSE_AUDIO_CMD_BASE = ["pactl"]
PULSE_AUDIO_FALLBACK_SINK = os.environ.get(
    "PLAYLIST_PULSE_AUDIO_FALLBACK_SINK", ""
).strip()
PULSE_AUDIO_FALLBACK_ENABLED = os.environ.get(
    "PLAYLIST_PULSE_AUDIO_FALLBACK_ENABLED", "0"
).strip().lower() in {"1", "true", "yes", "on"}
_PULSEAUDIO_OUTPUT_ADAPTER = PulseAudioOutputAdapter(
    tuple(_PULSE_AUDIO_CMD_BASE),
    timeout=PULSE_AUDIO_TIMEOUT,
    wait_timeout=PULSE_AUDIO_WAIT_TIMEOUT,
    poll_interval=PULSE_AUDIO_POLL_INTERVAL,
    fallback_sink=PULSE_AUDIO_FALLBACK_SINK or None,
    fallback_enabled=PULSE_AUDIO_FALLBACK_ENABLED,
)

ESP32_DEFAULT_CONFIG = {"host": "", "port": 80, "enabled": False}
ESP32_BUTTON_COUNT = 3
ESP32_TOTAL_TIMEOUT = float(os.environ.get("PLAYLIST_ESP32_TIMEOUT", "3.0"))
ESP32_CONNECT_TIMEOUT = float(
    os.environ.get("PLAYLIST_ESP32_CONNECT_TIMEOUT", "1.0")
)
# ``urllib`` exposes one socket timeout. Use the stricter ceiling so both the
# connection limit and the request-wide limit remain enforced at this layer.
ESP32_HTTP_TIMEOUT = min(ESP32_CONNECT_TIMEOUT, ESP32_TOTAL_TIMEOUT)
ESP32_STATUS_INTERVAL = max(
    1.0, float(os.environ.get("PLAYLIST_ESP32_STATUS_INTERVAL", "5"))
)
ESP32_STATUS_INITIAL_BACKOFF = max(
    0.1, float(os.environ.get("PLAYLIST_ESP32_STATUS_INITIAL_BACKOFF", "5"))
)
ESP32_STATUS_MAX_BACKOFF = max(
    ESP32_STATUS_INITIAL_BACKOFF,
    float(os.environ.get("PLAYLIST_ESP32_STATUS_MAX_BACKOFF", "60")),
)
ESP32_STATUS_FAILURE_THRESHOLD = max(
    1, int(os.environ.get("PLAYLIST_ESP32_STATUS_FAILURE_THRESHOLD", "3"))
)
ESP32_STATUS_CIRCUIT_COOLDOWN = max(
    0.1, float(os.environ.get("PLAYLIST_ESP32_STATUS_CIRCUIT_COOLDOWN", "30"))
)
_ESP32_OPERATION_LOCK = threading.RLock()
_esp32_supervisor: ESP32Supervisor | None = None

VOLUME_ACTIONS = {"up", "down", "mute", "set"}

ALL_SESSIONS_BUTTON_CATEGORY = "Tous"
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
_BT_PAIRED_RE = re.compile(r"\bPaired:\s*(yes|no)\b", re.IGNORECASE)
_BT_TRUSTED_RE = re.compile(r"\bTrusted:\s*(yes|no)\b", re.IGNORECASE)

BT_DEVICE_ADDR = os.environ.get("PLAYLIST_BT_DEVICE_ADDR", "").strip().upper()
BT_RECONNECT_INTERVAL = max(
    0.0, float(os.environ.get("PLAYLIST_BT_RECONNECT_INTERVAL", "10"))
)
BT_RECONNECT_MAX_ATTEMPTS = max(
    1, int(os.environ.get("PLAYLIST_BT_RECONNECT_MAX_ATTEMPTS", "3"))
)
BT_RECONNECT_CONNECT_TIMEOUT = max(
    0.1, float(os.environ.get("PLAYLIST_BT_RECONNECT_CONNECT_TIMEOUT", "3"))
)
BT_RECONNECT_INITIAL_DELAY = max(
    0.0, float(os.environ.get("PLAYLIST_BT_RECONNECT_INITIAL_DELAY", "0.5"))
)
BT_RECONNECT_MAX_DELAY = max(
    BT_RECONNECT_INITIAL_DELAY,
    float(os.environ.get("PLAYLIST_BT_RECONNECT_MAX_DELAY", "8")),
)
_bt_reconnect_cancel = threading.Event()
_bt_reconnect_controller: BluetoothReconnectController | None = None
_bt_reconnect_worker: BluetoothReconnectWorker | None = None
_bt_reconnect_policy_lock = threading.Lock()
_bt_state_cache: dict[str, dict[str, Any]] = {}
_bt_state_cache_lock = threading.Lock()
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
    primary_forward = forwarded_for.split(",")[0].strip() if forwarded_for else None
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
    return _redact_sensitive_text(text)


def _redact_sensitive_text(value: object) -> str:
    """Keep diagnostics useful without copying credentials into logs/HTTP."""
    text = str(value)
    if ACCUEIL_WEBHOOK_URL:
        text = text.replace(ACCUEIL_WEBHOOK_URL, "<redacted-webhook-url>")
    text = re.sub(
        r"(?i)(https?://)([^/\s:@]+):([^@\s/]+)@",
        r"\1<redacted-credentials>@",
        text,
    )
    text = re.sub(
        r"(?i)\b(token|secret|password|passwd|api[_-]?key)(\s*[=:]\s*)[^\s,;]+",
        r"\1\2<redacted>",
        text,
    )
    return text


def _bluetoothctl_script(*lines: str) -> subprocess.CompletedProcess:
    script_lines = [line for line in lines if line]
    needs_back = script_lines and script_lines[0].startswith("menu ")
    effective_lines = list(script_lines)
    if needs_back:
        effective_lines.append("back")
    effective_lines.append("quit")
    joined = "; ".join(effective_lines)
    proc = _BLUETOOTH_COMMAND_RUNNER.run(effective_lines)
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


def _bluetoothctl_direct(
    *arguments: str, timeout_s: float | None = None
) -> subprocess.CompletedProcess:
    """Run one bluetoothctl command under an external Linux timeout."""
    command_timeout = max(
        0.1,
        float(
            BT_CONNECT_COMMAND_TIMEOUT
            if timeout_s is None
            else timeout_s
        ),
    )
    if os.name == "nt":
        command = None
        direct_arguments = arguments
    else:
        command = ("timeout",)
        direct_arguments = (f"{command_timeout:.3f}s", *_VOLUME_CMD_BASE, *arguments)
    try:
        proc = _BLUETOOTH_COMMAND_RUNNER.run_args(
            direct_arguments,
            timeout=command_timeout + 5,
            command=command,
        )
    except Exception:
        servo_logger.logger.exception("BTCTL_DIRECT_ERROR")
        raise
    proc.stdout = _clean_bt_output(proc.stdout)
    proc.stderr = _clean_bt_output(proc.stderr)
    return proc


def _bluetoothctl_connect(
    address: str, *, timeout_s: float | None = None
) -> subprocess.CompletedProcess:
    """Connect without sending an immediate interactive ``quit`` command."""
    return _bluetoothctl_direct(
        "--agent",
        "NoInputNoOutput",
        "connect",
        address,
        timeout_s=timeout_s,
    )


def _serialized_bluetooth_operation(function):
    """Prevent overlapping multi-command scans and pairing workflows."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        with _BLUETOOTH_COMMAND_RUNNER.operation():
            return function(*args, **kwargs)

    return wrapper


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
        address = validate_bluetooth_address(address)
    except ValueError:
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
    paired = None
    trusted = None

    m = _BT_CONNECTED_RE.search(stdout)
    if m:
        connected = m.group(1).lower() == "yes"
    m = _BT_PAIRED_RE.search(stdout)
    if m:
        paired = m.group(1).lower() == "yes"
    m = _BT_TRUSTED_RE.search(stdout)
    if m:
        trusted = m.group(1).lower() == "yes"

    result = {
        "connected": connected,
        "paired": paired,
        "trusted": trusted,
        "audio_sink_capable": has_audio_sink_profile(parse_bluez_uuids(stdout)),
        "raw": stdout,
    }
    with _bt_state_cache_lock:
        _bt_state_cache[address] = dict(result)
    return result


def _cached_bluetooth_info(
    address: str, result: ReconnectResult | None = None
) -> dict[str, Any] | None:
    """Read the last published state without waiting on the Bluetooth tool."""
    with _bt_state_cache_lock:
        cached = _bt_state_cache.get(address)
    if cached is not None:
        return dict(cached)
    if result is not None and isinstance(result.state, dict):
        return dict(result.state)
    return None


def _wait_bt_flag(
    address: str, key: str, desired: bool, timeout_s: float, interval: float = 0.5
) -> bool:
    """Poll bluetoothctl info until key (connected/paired/trusted) matches desired or timeout."""
    deadline = time.time() + max(0.1, float(timeout_s))
    while time.time() < deadline:
        info = _bluetooth_info(address)
        if info is None:
            time.sleep(interval)
            continue
        value = info.get(key)
        if isinstance(value, bool) and value == desired:
            return True
        time.sleep(interval)
    return False


def _connect_bt_once(address: str, timeout_s: float) -> bool:
    try:
        proc = _bluetoothctl_connect(address, timeout_s=timeout_s)
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    return _wait_bt_flag(
        address,
        "connected",
        True,
        timeout_s=timeout_s,
        interval=min(0.2, max(0.05, timeout_s / 4)),
    )


def _get_bt_reconnect_controller() -> BluetoothReconnectController:
    global _bt_reconnect_controller
    if _bt_reconnect_controller is None:
        _bt_reconnect_controller = BluetoothReconnectController(
            read_state=_bluetooth_info,
            connect_once=_connect_bt_once,
            max_attempts=BT_RECONNECT_MAX_ATTEMPTS,
            connect_timeout=BT_RECONNECT_CONNECT_TIMEOUT,
            initial_delay=BT_RECONNECT_INITIAL_DELAY,
            max_delay=BT_RECONNECT_MAX_DELAY,
            cancel_event=_bt_reconnect_cancel,
            log_attempt=lambda message: servo_logger.logger.info(
                "BTCTL_RECONNECT_ATTEMPT | %s", message
            ),
        )
    return _bt_reconnect_controller


def _run_bt_reconnect_policy(address: str) -> ReconnectResult:
    with _bt_reconnect_policy_lock:
        return _get_bt_reconnect_controller().ensure(address)


def _on_bt_reconnect_result(result: ReconnectResult) -> None:
    if not result.connected:
        return
    try:
        _ensure_bt_audio_output(result.address)
    except Exception:
        servo_logger.logger.info("BT_AUDIO_OUTPUT_PENDING")


def _start_bt_reconnect_worker(address: str) -> None:
    global _bt_reconnect_worker
    if _bt_reconnect_worker is None:
        _bt_reconnect_worker = BluetoothReconnectWorker(
            reconnect=_run_bt_reconnect_policy,
            retry_interval=BT_RECONNECT_INTERVAL or 10.0,
            on_result=_on_bt_reconnect_result,
        )
    _bt_reconnect_worker.start(address)


def _ensure_bt_connection(address: str, *, max_attempts: int | None = None) -> bool:
    if not address:
        return True
    try:
        normalized = validate_bluetooth_address(address)
    except ValueError:
        servo_logger.logger.warning("BTCTL_RECONNECT_INVALID_ADDRESS")
        return False
    with _bt_reconnect_policy_lock:
        result = _get_bt_reconnect_controller().ensure(
            normalized, max_attempts=max_attempts
        )
    if not result.connected and result.reason not in {"not_trusted", "cancelled"}:
        servo_logger.logger.warning(
            "BTCTL_RECONNECT_DEGRADED | attempts=%s | reason=%s",
            result.attempts,
            result.reason,
        )
    return result.connected


def _ensure_bt_audio_output(address: str) -> bool:
    """Require an independently verified A2DP sink before starting audio."""
    state = _bt_ui_state(address)
    if (
        state
        and state.get("connected") is True
        and state.get("audio_sink_capable") is True
        and state.get("pulse_sink")
        and state.get("pulse_default") is True
        and state.get("pulse_state") != "SUSPENDED"
    ):
        return True
    try:
        _bt_ui_select_output(address)
        return True
    except Exception:
        servo_logger.logger.warning("BT_AUDIO_OUTPUT_UNAVAILABLE")
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


def _run_volume_action(
    action: str, target_value: int | None = None
) -> tuple[bool, str, int | None]:
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
            return (
                False,
                "Aucun transport bluetooth actif (peripherique connecte ?)",
                None,
            )

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


# --- Playlist and current playback entry (domain façade) ---
PlaylistManager = PlaylistStore
playlist = PlaylistManager()
_playback_state = PlaybackStateStore()


# Keep ESP32 relay active for a brief window while the next track loads
TRANSITION_HOLD_SECONDS = float(os.environ.get("PLAYLIST_TRANSITION_HOLD", "4.0"))
_TRANSITION_HOLD_REASONS = {"completed", "skip"}
_transition_state_lock = threading.Lock()
_last_finish_ts: float = 0.0
_last_finish_reason: Optional[str] = None


def _set_current_entry(entry: Optional[dict[str, Any]]) -> None:
    _playback_state.set_current(entry)


def _get_current_entry() -> Optional[dict[str, Any]]:
    return _playback_state.get_current()


_random_lock = threading.Lock()
_RANDOM_EXCLUDED_NAMES = {"Accueil"}
_random_selector = RandomSessionSelector()
_random_enabled = False
_random_last_pick: Optional[dict[str, Any]] = None


def _normalize_session_name(name: str) -> str:
    return name.strip().lower()


def _list_session_names() -> list[str]:
    try:
        return list(SessionCatalog(DATA_DIR).list_names())
    except Exception as exc:
        servo_logger.logger.warning("SESSION_LIST_FAILED | error=%s", exc)
        return []


def _eligible_random_sessions(additional_excludes: Iterable[str] = ()) -> list[str]:
    excluded = list(_RANDOM_EXCLUDED_NAMES) + list(additional_excludes)
    return list(_random_selector.eligible(_list_session_names(), excluded))


def _pick_random_session(additional_excludes: Iterable[str] = ()) -> Optional[str]:
    candidates = _eligible_random_sessions(additional_excludes)
    if not candidates:
        return None
    return _random_selector.choose(candidates)


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
    return SessionCatalog(DATA_DIR).resolve(session_name)


def _ensure_session_exists(session_name: str) -> Path:
    try:
        return SessionCatalog(DATA_DIR).require_playable(session_name)
    except FileNotFoundError:
        raise InvalidInputError(f"Session introuvable: {session_name}") from None


def _start_session(
    session_name: str, source: str, item_id: Optional[int] = None
) -> bool:
    def _maybe_trigger_accueil_webhook(name: str) -> None:
        if not ACCUEIL_WEBHOOK_URL:
            return
        if _normalize_session_name(name) != "accueil":
            return
        curl_cmd = [
            "curl",
            "-sS",
            "-X",
            "POST",
            ACCUEIL_WEBHOOK_URL,
        ]
        try:
            completed = subprocess.run(
                curl_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=ACCUEIL_WEBHOOK_TIMEOUT,
                check=False,
            )
            if completed.returncode == 0:
                servo_logger.logger.info("ACCUEIL_WEBHOOK_TRIGGERED | session=%s", name)
            else:
                servo_logger.logger.warning(
                    "ACCUEIL_WEBHOOK_FAILED | session=%s | code=%s | stderr=%s",
                    name,
                    completed.returncode,
                    _redact_sensitive_text(
                        completed.stderr.decode("utf-8", errors="ignore")
                    ),
                )
        except subprocess.TimeoutExpired:
            servo_logger.logger.warning(
                "ACCUEIL_WEBHOOK_TIMEOUT | session=%s | timeout=%.1fs",
                name,
                ACCUEIL_WEBHOOK_TIMEOUT,
            )
        except FileNotFoundError:
            servo_logger.logger.error(
                "ACCUEIL_WEBHOOK_CURL_MISSING | session=%s | cmd=%s",
                name,
                " ".join(_redact_sensitive_text(part) for part in curl_cmd),
            )
        except Exception as exc:
            servo_logger.logger.warning(
                "ACCUEIL_WEBHOOK_UNEXPECTED_ERROR | session=%s | type=%s",
                name,
                type(exc).__name__,
            )

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
        if not _ensure_bt_audio_output(BT_DEVICE_ADDR):
            servo_logger.logger.error(
                "PLAYLIST_BT_AUDIO_OUTPUT_FAILED | session=%s | source=%s",
                session_name,
                source,
            )
            return False

    try:
        _legacy_playback_service().start(session_dir)
    except Exception as exc:
        servo_logger.logger.error(
            f"PLAYLIST_START_FAILED | session={session_name} | error={exc}"
        )
        return False

    _maybe_trigger_accueil_webhook(session_name)
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
        session_name = next_item.get("session")
        if session_name and _normalize_session_name(session_name) == "accueil":
            queue_cleared = False
            try:
                queue_cleared = playlist.has_items()
            except Exception:
                queue_cleared = False
            if queue_cleared:
                playlist.clear()
            servo_logger.logger.info(
                "ACCUEIL_PRIORITY_PLAYLIST | cleared_queue=%s | next_id=%s",
                queue_cleared,
                next_item.get("id"),
            )
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

        try:
            loop_player.release_suppression(delay=5.0)
        except Exception:
            servo_logger.logger.exception("LOOP_RESUME_SCHEDULE_FAILED")

    if reason in {"completed", "skip", "error"}:
        threading.Thread(target=_start_next_from_playlist, daemon=True).start()


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
        _write_json_atomic(ESP32_BUTTON_ASSIGNMENTS_PATH, {"assignments": sanitized})
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
    if normalized == ALL_SESSIONS_BUTTON_CATEGORY.strip().lower():
        sessions = _eligible_random_sessions()
    else:
        sessions = []
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


def _button_category_options() -> list[str]:
    data = _load_session_categories()
    categories = data["categories"]
    result: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        label = (value or "").strip()
        if not label:
            return
        key = label.lower()
        if key in seen:
            return
        seen.add(key)
        result.append(label)

    _add(ALL_SESSIONS_BUTTON_CATEGORY)
    for item in categories:
        _add(item)
    return result


def _resolve_session_candidate(value: str) -> tuple[str, Optional[str]]:
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError("Session vide")
    matching = _sessions_for_category(candidate)
    if matching:
        return _random_selector.choose(matching), candidate
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
    log_suffix = f" | {context_bits}" if context_bits else ""

    normalized_session = _normalize_session_name(session_name)
    is_accueil = normalized_session == "accueil"
    queue_cleared = False
    forced_replace = False

    try:
        status_info = player.status()
    except Exception:
        status_info = {}
    is_running = bool(status_info.get("running"))
    was_running = is_running

    if is_accueil:
        try:
            queue_cleared = playlist.has_items()
        except Exception:
            queue_cleared = False
        if queue_cleared:
            playlist.clear()

        if was_running:
            previous_session = status_info.get("session")
            try:
                _legacy_playback_service().stop(reason="replace")
                forced_replace = True
            except Exception:
                servo_logger.logger.exception(
                    "ACCUEIL_FORCE_STOP_FAILED | requested=%s", session_name
                )
            finally:
                _set_current_entry(None)
            is_running = False

        servo_logger.logger.info(
            "ACCUEIL_PRIORITY | cleared_queue=%s | stop_attempted=%s | stop_succeeded=%s | source=%s%s",
            queue_cleared,
            was_running,
            forced_replace,
            source,
            log_suffix,
        )

    if is_running and not is_accueil:
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
        with _ESP32_OPERATION_LOCK:
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
            _redact_sensitive_text(body[:200]),
        )
        raise ESP32CommunicationError(f"Erreur HTTP ESP32 ({exc.code})") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        servo_logger.logger.warning(
            "ESP32_UNREACHABLE | method=%s | path=%s | reason=%s",
            method,
            path,
            type(reason).__name__,
        )
        raise ESP32CommunicationError("Connexion ESP32 indisponible.") from exc
    except ESP32ConfigError:
        raise
    except Exception as exc:
        servo_logger.logger.warning(
            "ESP32_UNEXPECTED_ERROR | method=%s | path=%s | type=%s",
            method,
            path,
            type(exc).__name__,
        )
        raise ESP32CommunicationError("Communication ESP32 impossible.") from exc


def _esp32_probe_status() -> Dict[str, Any]:
    return _esp32_request("/api/status", method="GET")


def _esp32_is_enabled() -> bool:
    return bool(load_esp32_config().get("enabled"))


def _start_esp32_supervisor() -> None:
    global _esp32_supervisor
    if _esp32_supervisor is None:
        _get_esp32_supervisor()
    _esp32_supervisor.start()
    _esp32_supervisor.wake()


def _get_esp32_supervisor() -> ESP32Supervisor:
    global _esp32_supervisor
    if _esp32_supervisor is None:
        _esp32_supervisor = ESP32Supervisor(
            probe=_esp32_probe_status,
            enabled=_esp32_is_enabled,
            interval=ESP32_STATUS_INTERVAL,
            initial_backoff=ESP32_STATUS_INITIAL_BACKOFF,
            max_backoff=ESP32_STATUS_MAX_BACKOFF,
            failure_threshold=ESP32_STATUS_FAILURE_THRESHOLD,
            circuit_cooldown=ESP32_STATUS_CIRCUIT_COOLDOWN,
        )
    return _esp32_supervisor


def _esp32_public_status(*, manual_probe: bool = False) -> Dict[str, Any]:
    if _esp32_is_enabled():
        supervisor = _get_esp32_supervisor()
        if _runtime_initialized:
            _start_esp32_supervisor()
        snapshot = (
            supervisor.manual_probe()
            if manual_probe
            else supervisor.snapshot()
        )
    elif _esp32_supervisor is not None:
        _esp32_supervisor.wake()
        snapshot = _esp32_supervisor.snapshot()
    else:
        snapshot = ESP32ProbeSnapshot()
    response: Dict[str, Any] = {
        "reachable": snapshot.reachable,
        "supervision": snapshot.public(),
    }
    if snapshot.reachable and snapshot.payload is not None:
        response["status"] = dict(snapshot.payload)
    else:
        if snapshot.state == "probing":
            response["error"] = "Vérification ESP32 déjà en cours."
            response["reason"] = "busy"
        else:
            response["error"] = (
                "ESP32 indisponible."
                if snapshot.state != "disabled"
                else "Pilotage ESP32 desactive."
            )
            response["reason"] = (
                "network" if snapshot.state != "disabled" else "config"
            )
    return response


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


@legacy_api.route("/esp32/config", methods=["GET"])
def esp32_get_config():
    config = load_esp32_config()
    payload = dict(config)
    payload["buttonCount"] = ESP32_BUTTON_COUNT
    return jsonify(payload)


@legacy_api.route("/esp32/config", methods=["POST"])
def esp32_update_config():
    body = request.get_json(silent=True) or {}
    try:
        updated = update_esp32_config(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    payload = dict(updated)
    payload["buttonCount"] = ESP32_BUTTON_COUNT
    if payload.get("enabled") and _runtime_initialized:
        _start_esp32_supervisor()
    elif _esp32_supervisor is not None:
        _esp32_supervisor.wake()
    return jsonify(payload)


@legacy_api.route("/esp32/status")
def esp32_status():
    try:
        manual_probe = request.args.get("probe", "").strip().lower() == "manual"
        return jsonify(_esp32_public_status(manual_probe=manual_probe))
    except ESP32ConfigError as exc:
        return jsonify(_esp32_response_error(str(exc), reason="config"))
    except ESP32CommunicationError as exc:
        return jsonify(_esp32_response_error(str(exc), reason="network"))


@legacy_api.route("/esp32/status/check", methods=["POST"])
def esp32_status_check():
    try:
        response = _esp32_public_status(manual_probe=True)
        status_code = 202 if response.get("supervision", {}).get("busy") else 200
        return jsonify(response), status_code
    except ESP32ConfigError as exc:
        return jsonify(_esp32_response_error(str(exc), reason="config"))
    except ESP32CommunicationError as exc:
        return jsonify(_esp32_response_error(str(exc), reason="network"))


@legacy_api.route("/esp32/relay", methods=["POST"])
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


@legacy_api.route("/esp32/auto-relay", methods=["POST"])
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


@legacy_api.route("/esp32/button-config", methods=["GET"])
def esp32_button_config():
    assignments = _load_button_assignments()
    categories = _button_category_options()
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
        response["categories"] = categories
        if isinstance(states, list):
            response["states"] = states
        return jsonify(response)
    except ESP32ConfigError as exc:
        error = _esp32_response_error(str(exc), reason="config")
        error["assignments"] = assignments
        error["buttonCount"] = ESP32_BUTTON_COUNT
        error["sessions"] = assignments
        error["categories"] = categories
        return jsonify(error)
    except ESP32CommunicationError as exc:
        error = _esp32_response_error(str(exc), reason="network")
        error["assignments"] = assignments
        error["buttonCount"] = ESP32_BUTTON_COUNT
        error["sessions"] = assignments
        error["categories"] = categories
        return jsonify(error)


@legacy_api.route("/esp32/button-config", methods=["POST"])
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


@legacy_api.route("/esp32/button/<int:button_index>/play", methods=["POST"])
def esp32_button_play(button_index: int):
    if button_index < 0 or button_index >= ESP32_BUTTON_COUNT:
        return (
            jsonify(
                {"error": f"Index bouton hors limites (0-{ESP32_BUTTON_COUNT - 1})."}
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
        return (
            jsonify(
                {
                    "error": f"Aucune session disponible pour la categorie '{category}'.",
                    "category": category,
                }
            ),
            404,
        )

    chosen_session = _random_selector.choose(sessions)
    payload, status_code = _trigger_session_for_button(
        chosen_session, button_index, category
    )
    payload["category"] = category
    payload["session"] = chosen_session
    payload["button"] = button_index
    payload["available_sessions"] = sessions
    return jsonify(payload), status_code


@legacy_api.route("/esp32/restart", methods=["POST"])
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


def _sanitize_loop_filename(filename: str) -> str:
    """Sanitize uploaded loop file names."""
    if not filename:
        return "loop.mp3"
    base = Path(filename).name
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", base).strip("._")
    if not cleaned:
        cleaned = "loop"
    if not cleaned.lower().endswith(".mp3"):
        cleaned = f"{cleaned}.mp3"
    return cleaned[:80]


@legacy_api.route("/")
def index():
    return render_template("index.html")


@legacy_api.route("/favicon.ico")
def favicon():
    return send_from_directory(
        app.static_folder, "SkullPlayer.png", mimetype="image/png"
    )


@legacy_api.route("/upload", methods=["POST"])
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


@legacy_api.route("/loop/status")
def loop_status():
    try:
        return jsonify(loop_player.status())
    except Exception as exc:
        servo_logger.logger.exception("LOOP_STATUS_ERROR")
        return jsonify({"error": str(exc)}), 500


@legacy_api.route("/loop/enable", methods=["POST"])
def loop_enable():
    payload = request.get_json(silent=True) or {}
    if "enabled" not in payload:
        return jsonify({"error": "Champ 'enabled' manquant"}), 400
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        return jsonify({"error": "Le champ 'enabled' doit etre booleen"}), 400
    try:
        changed = loop_player.set_enabled(enabled)
    except Exception as exc:
        servo_logger.logger.exception("LOOP_ENABLE_ERROR")
        return jsonify({"error": str(exc)}), 500

    status = loop_player.status()
    status["changed"] = changed
    return jsonify(status)


@legacy_api.route("/loop/upload", methods=["POST"])
def loop_upload():
    try:
        up_file = request.files.get("loop_mp3")
        if not up_file or not up_file.filename:
            return jsonify({"error": "Fichier MP3 requis"}), 400

        original_name = up_file.filename
        safe_name = _sanitize_loop_filename(original_name)

        tmp_handle = tempfile.NamedTemporaryFile(
            dir=str(LOOP_AUDIO_DIR), suffix=".mp3", delete=False
        )
        tmp_path = Path(tmp_handle.name)
        tmp_handle.close()
        try:
            up_file.save(str(tmp_path))
            final_path = LOOP_AUDIO_DIR / safe_name
            shutil.move(str(tmp_path), final_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

        try:
            loop_player.replace_audio(final_path, display_name=original_name)
        except ValueError as exc:
            try:
                final_path.unlink()
            except Exception:
                pass
            return jsonify({"error": str(exc)}), 400

        # Clean up older loop files to avoid clutter.
        for leftover in LOOP_AUDIO_DIR.glob("*.mp3"):
            if leftover != final_path:
                try:
                    leftover.unlink()
                except Exception:
                    servo_logger.logger.warning(
                        "LOOP_FILE_CLEANUP_FAILED | file=%s", leftover
                    )

        status = loop_player.status()
        status["filename"] = original_name
        return jsonify({"status": "ok", "loop": status})
    except Exception as exc:
        servo_logger.logger.exception("LOOP_UPLOAD_ERROR")
        return jsonify({"error": f"Echec upload boucle: {exc}"}), 500


@legacy_api.route("/loop/volume", methods=["POST"])
def loop_volume():
    """
    Régler le volume de la boucle.
    Body JSON attendu:
      { "volume": 0.7, "fade_ms": 600 }
    Notes:
      - volume peut aussi être en pourcentage (ex: 70 -> 0.7)
      - fade_ms est optionnel (par défaut: self.fade_ms côté LoopPlayer)
    """
    payload = request.get_json(silent=True) or {}
    if "volume" not in payload:
        return jsonify({"error": "Champ 'volume' manquant"}), 400

    raw_vol = payload.get("volume")
    try:
        vol = float(raw_vol)
    except (TypeError, ValueError):
        return jsonify({"error": "Volume invalide"}), 400

    # Autoriser 0..1 ou 0..100 (auto-détection)
    if vol > 1.0:
        # interpréter comme pourcentage si plausible
        if 0.0 <= vol <= 100.0:
            vol = vol / 100.0

    # Clamp 0..1
    vol = max(0.0, min(1.0, vol))

    fade_ms = payload.get("fade_ms", None)
    try:
        loop_player.set_volume(vol, fade_ms=fade_ms)
        st = loop_player.status()
        return jsonify({"status": "ok", "loop": st})
    except Exception as exc:
        servo_logger.logger.exception("LOOP_VOLUME_ERROR")
        return jsonify({"error": str(exc)}), 500


@legacy_api.route("/sessions")
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


@legacy_api.route("/api/sessions", methods=["GET"])
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
        current_entry.get("session") if isinstance(current_entry, dict) else None
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


@legacy_api.route("/sessions/<session_name>/category", methods=["PUT"])
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


@legacy_api.route("/categories", methods=["GET", "POST"])
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


@legacy_api.route("/sessions/<session_name>", methods=["DELETE"])
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
            _legacy_playback_service().stop(reason="skip")
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


@legacy_api.route("/play", methods=["POST"])
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


@legacy_api.route("/api/enqueue", methods=["POST"])
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
        logger_fn = (
            servo_logger.logger.error
            if status_code >= 500
            else servo_logger.logger.warning
        )
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


@legacy_api.route("/pause", methods=["POST"])
def pause():
    try:
        _legacy_playback_service().pause()
        return jsonify({"status": "paused"})
    except Exception as e:
        return jsonify({"error": f"Erreur pause: {e}"}), 500


@legacy_api.route("/resume", methods=["POST"])
def resume():
    try:
        _legacy_playback_service().resume()
        return jsonify({"status": "resumed"})
    except Exception as e:
        return jsonify({"error": f"Erreur resume: {e}"}), 500


@legacy_api.route("/stop", methods=["POST"])
def stop():
    try:
        _legacy_playback_service().stop()
        _set_current_entry(None)
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": f"Erreur stop: {e}"}), 500


@legacy_api.route("/status")
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
            reconnect_result = (
                _bt_reconnect_worker.last_result
                if _bt_reconnect_worker is not None
                else _get_bt_reconnect_controller().last_result
            )
            worker_busy = bool(
                _bt_reconnect_worker is not None
                and getattr(_bt_reconnect_worker, "busy", False)
            )
            if _bt_reconnect_worker is not None:
                # The worker owns the BlueZ command lock. Never wait for it from
                # this read-only route; use the last published snapshot instead.
                info = _cached_bluetooth_info(BT_DEVICE_ADDR, reconnect_result)
            else:
                info = _bluetooth_info(BT_DEVICE_ADDR)
            connected = info.get("connected") if info else None
            volume_percent: int | None = None

            selected_output = (
                None
                if worker_busy
                else _PULSEAUDIO_OUTPUT_ADAPTER.selected_for(BT_DEVICE_ADDR)
            )
            audio_sink_capable = info.get("audio_sink_capable") if info else None
            audio_ready = bool(
                connected is True
                and audio_sink_capable is True
                and selected_output
                and selected_output.get("pulse_default") is True
                and selected_output.get("pulse_state") != "SUSPENDED"
            )
            if worker_busy:
                connection_state = "reconnecting"
            elif audio_ready:
                connection_state = "audio_ready"
            elif reconnect_result is not None and reconnect_result.reason in {
                "degraded",
                "state_unavailable",
                "not_trusted",
                "worker_error",
                "cancelled",
            }:
                connection_state = "degraded"
            elif connected is True:
                connection_state = "connected"
            elif connected is False:
                connection_state = "disconnected"
            else:
                connection_state = "unknown"

            if info and connected is True and not worker_busy:
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
                "paired": info.get("paired") if info else None,
                "trusted": info.get("trusted") if info else None,
                "connected": connected,
                "connection_state": connection_state,
                "audio_sink_capable": audio_sink_capable,
                "pulse_sink": selected_output.get("pulse_sink") if selected_output else None,
                "audio_ready": audio_ready,
                "last_attempt_ts": (
                    _bt_reconnect_worker.last_attempt_ts
                    if _bt_reconnect_worker is not None
                    else None
                ),
                "retry_interval": BT_RECONNECT_INTERVAL,
            }
            if reconnect_result is not None:
                st["bluetooth"]["reconnect"] = {
                    "attempts": reconnect_result.attempts,
                    "reason": reconnect_result.reason,
                }
            if volume_percent is not None:
                st["bluetooth"]["volume_percent"] = volume_percent
        st["loop"] = loop_player.status()
        return jsonify(st)
    except Exception as e:
        return jsonify({"error": f"Erreur status: {e}"}), 500


@legacy_api.route("/random_mode", methods=["GET", "POST"])
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


@legacy_api.route("/volume", methods=["POST"])
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


@legacy_api.route("/playlist", methods=["GET", "POST"])
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


@legacy_api.route("/playlist/shuffle", methods=["POST"])
def playlist_shuffle():
    sessions = _eligible_random_sessions()
    if not sessions:
        return (
            jsonify({"error": "Aucune session disponible pour la lecture aléatoire"}),
            400,
        )

    _random_selector.shuffle(sessions)

    try:
        _legacy_playback_service().stop(reason="shuffle")
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
            "playlist": _enrich_queue_with_categories(playlist.snapshot(), mapping),
        }
    )


@legacy_api.route("/playlist/<int:item_id>", methods=["DELETE"])
def playlist_delete(item_id: int):
    removed = playlist.remove(item_id)
    if not removed:
        return jsonify({"error": "Element introuvable"}), 404
    servo_logger.logger.info(
        f"PLAYLIST_REMOVE | id={item_id} | session={removed['session']}"
    )
    enriched = _enrich_entry_with_category(removed)
    return jsonify({"status": "removed", "item": enriched})


@legacy_api.route("/playlist/<int:item_id>/move", methods=["POST"])
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


@legacy_api.route("/playlist/skip", methods=["POST"])
def playlist_skip():
    try:
        status_info = player.status()
        if status_info.get("running"):
            servo_logger.logger.info("PLAYLIST_SKIP_REQUEST | state=running")
            _legacy_playback_service().stop(reason="skip")
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


@legacy_api.route("/service/restart", methods=["POST"])
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


@legacy_api.route("/bluetooth/restart", methods=["POST"])
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


# -------------------- Bluetooth pairing API --------------------


def _parse_bt_devices_list(text: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    if not text:
        return devices
    for line in (text or "").splitlines():
        line = line.strip()
        # Expected: "Device AA:BB:CC:DD:EE:FF Name Of Device"
        if not line.startswith("Device "):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            continue
        mac = parts[1].strip()
        name = parts[2].strip() if len(parts) > 2 else ""
        try:
            mac = validate_bluetooth_address(mac)
        except ValueError:
            continue
        devices.append({"mac": mac, "name": name})
    return devices


@legacy_api.route("/scan", methods=["POST"])
@_serialized_bluetooth_operation
def bt_scan():
    try:
        _ = _bluetoothctl_script("power on")
        _ = _bluetoothctl_script("agent on")
        _ = _bluetoothctl_script("default-agent")
        _ = _bluetoothctl_script("scan on")
        time.sleep(5)
        _ = _bluetoothctl_script("scan off")
        proc = _bluetoothctl_script("devices")
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scan bluetooth timeout"}), 504
    except Exception as e:
        servo_logger.logger.exception("BT_SCAN_ERROR")
        return jsonify({"error": f"Scan bluetooth impossible: {e}"}), 500

    devices = _parse_bt_devices_list(proc.stdout or "")
    return jsonify(devices)


@legacy_api.route("/pair", methods=["POST"])
@_serialized_bluetooth_operation
def bt_pair():
    data = request.get_json(silent=True) or {}
    mac = (data.get("mac") or data.get("address") or "").strip()
    if not mac:
        return jsonify({"error": "mac address required"}), 400
    try:
        mac = validate_bluetooth_address(mac)
    except ValueError:
        return jsonify({"error": "invalid mac address"}), 400

    results: dict[str, dict[str, object]] = {}

    def run(cmd: str) -> subprocess.CompletedProcess:
        proc = _bluetoothctl_script(cmd)
        results[cmd] = {
            "stdout": (proc.stdout or ""),
            "stderr": (proc.stderr or ""),
            "rc": int(proc.returncode),
        }
        return proc

    try:
        # Ensure controller is ready
        _ = _bluetoothctl_script("power on")
        _ = _bluetoothctl_script("agent on")
        _ = _bluetoothctl_script("default-agent")

        # 1) Pair
        p1 = run(f"pair {mac}")
        if p1.returncode != 0:
            return jsonify({"error": "pair_failed", "results": results}), 500
        if not _wait_bt_flag(mac, "paired", True, timeout_s=15.0):
            return jsonify({"error": "pair_timeout", "results": results}), 504

        # 2) Trust
        p2 = run(f"trust {mac}")
        if p2.returncode != 0:
            return jsonify({"error": "trust_failed", "results": results}), 500
        if not _wait_bt_flag(mac, "trusted", True, timeout_s=8.0):
            return jsonify({"error": "trust_timeout", "results": results}), 504

        # 3) Connect
        p3 = run(f"connect {mac}")
        if p3.returncode != 0:
            return jsonify({"error": "connect_failed", "results": results}), 500
        if not _wait_bt_flag(mac, "connected", True, timeout_s=12.0):
            return jsonify({"error": "connect_timeout", "results": results}), 504

        flags = _bluetooth_info(mac) or {}
        return jsonify(
            {
                "results": results,
                "status": {k: flags.get(k) for k in ("paired", "trusted", "connected")},
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "bluetoothctl_timeout", "results": results}), 504
    except Exception:
        servo_logger.logger.exception("BT_PAIR_ERROR")
        return jsonify({"error": "pair_unavailable", "results": results}), 500


# -------------------- Explicit Bluetooth UI operations --------------------


def _bt_ui_state(address: str) -> dict[str, Any] | None:
    """Return only independent, non-diagnostic state fields to the UI."""
    info = _bluetooth_info(address)
    if info is None:
        return None
    state = {
        "address": address,
        "paired": info.get("paired"),
        "trusted": info.get("trusted"),
        "connected": info.get("connected"),
        "discovered": True,
        "audio_sink_capable": info.get("audio_sink_capable"),
        "pulse_sink": None,
        "last_error": None,
    }
    selected = _PULSEAUDIO_OUTPUT_ADAPTER.selected_for(address)
    if selected:
        state.update(
            {
                "audio_sink_capable": True,
                "pulse_sink": selected.get("pulse_sink"),
                "pulse_default": selected.get("pulse_default"),
                "pulse_state": selected.get("pulse_state"),
                "fallback_used": selected.get("fallback_used", False),
            }
        )
    return state


@_serialized_bluetooth_operation
def _bt_ui_scan() -> list[dict[str, str]]:
    for command in ("power on", "agent on", "default-agent", "scan on"):
        proc = _bluetoothctl_script(command)
        if proc.returncode != 0:
            raise DependencyUnavailableError("Scan Bluetooth refuse")
    time.sleep(5)
    proc = _bluetoothctl_script("scan off")
    if proc.returncode != 0:
        raise DependencyUnavailableError("Scan Bluetooth refuse")
    devices = _bluetoothctl_script("devices")
    if devices.returncode != 0:
        raise DependencyUnavailableError("Scan Bluetooth refuse")
    return _parse_bt_devices_list(devices.stdout or "")


def _bt_ui_prepare() -> None:
    for command in ("power on", "agent on", "default-agent"):
        proc = _bluetoothctl_script(command)
        if proc.returncode != 0:
            raise DependencyUnavailableError("Agent Bluetooth indisponible")


@_serialized_bluetooth_operation
def _bt_ui_pair(address: str) -> dict[str, Any]:
    address = validate_bluetooth_address(address)
    current = _bluetooth_info(address)
    if current and current.get("paired") is True:
        return {"address": address, "paired": True}
    _bt_ui_prepare()
    proc = _bluetoothctl_script(f"pair {address}")
    if proc.returncode != 0:
        raise DependencyUnavailableError("Appairage Bluetooth refuse")
    if not _wait_bt_flag(address, "paired", True, timeout_s=15.0):
        raise TimeoutError("Appairage Bluetooth expire")
    return {"address": address, "paired": True}


@_serialized_bluetooth_operation
def _bt_ui_trust(address: str) -> dict[str, Any]:
    address = validate_bluetooth_address(address)
    current = _bluetooth_info(address)
    if current and current.get("trusted") is True:
        return {"address": address, "trusted": True}
    proc = _bluetoothctl_script(f"trust {address}")
    if proc.returncode != 0:
        raise DependencyUnavailableError("Confiance Bluetooth refusee")
    if not _wait_bt_flag(address, "trusted", True, timeout_s=8.0):
        raise TimeoutError("Confiance Bluetooth expiree")
    return {"address": address, "trusted": True}


@_serialized_bluetooth_operation
def _bt_ui_connect(address: str) -> dict[str, Any]:
    address = validate_bluetooth_address(address)
    current = _bluetooth_info(address)
    if current and current.get("connected") is True:
        return {"address": address, "connected": True}
    proc = _bluetoothctl_connect(address)
    if proc.returncode == 124:
        raise TimeoutError("Connexion Bluetooth expiree")
    if proc.returncode != 0:
        raise DependencyUnavailableError("Connexion Bluetooth refusee")
    if not _wait_bt_flag(address, "connected", True, timeout_s=12.0):
        raise TimeoutError("Connexion Bluetooth expiree")
    return {"address": address, "connected": True}


def _bt_ui_select_output(address: str) -> dict[str, Any]:
    """Select PulseAudio only after independent Bluetooth/A2DP proofs."""
    state = _bt_ui_state(address)
    if not state or state.get("connected") is not True:
        raise OperationNotAllowedError("Connexion Bluetooth requise")
    if state.get("audio_sink_capable") is not True:
        raise OperationNotAllowedError("Profil Audio Sink indisponible")
    return _PULSEAUDIO_OUTPUT_ADAPTER.select_for_bluetooth(address)


def _bt_ui_test_audio(address: str, duration_ms: int, volume: int) -> dict[str, Any]:
    """Keep physical playback behind the dedicated validation task."""
    raise OperationNotAllowedError("Test audio réservé à la validation matérielle")


# -------------------- Channels API --------------------


@legacy_api.route("/channels", methods=["GET", "POST"])
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


@legacy_api.route("/pitch", methods=["GET", "POST"])
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
@legacy_api.route("/logs")
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


@legacy_api.route("/logs/stream")
def logs_stream():
    """Serve a short SSE window so sync Gunicorn workers are not monopolized."""

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
                deadline = time.monotonic() + LOG_STREAM_WINDOW_SECONDS
                yield "retry: 1000\n\n"

                while time.monotonic() < deadline:
                    line = f.readline()
                    if line:
                        yield f"data: {line.rstrip()}\n\n"
                    else:
                        yield ": keep-alive\n\n"
                        remaining = deadline - time.monotonic()
                        if remaining > 0:
                            time.sleep(min(LOG_STREAM_POLL_INTERVAL, remaining))
        except Exception as e:
            yield f"data: Error reading log: {e}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@legacy_api.route("/logs/stats")
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
@legacy_api.route("/data/<path:filename>")
def data_file(filename):
    return send_from_directory(DATA_DIR, filename)


# Serve log files for download
@legacy_api.route("/logs/download")
def logs_download():
    """Télécharge le fichier de log actuel"""
    try:
        log_file = servo_logger.get_latest_log_file()
        if not log_file.exists():
            return "No log file found", 404
        return send_from_directory(log_file.parent, log_file.name, as_attachment=True)
    except Exception as e:
        return f"Error: {e}", 500


def _v1_session_basename(value: Any) -> Optional[str]:
    if not value:
        return None
    text = str(value).replace("\\", "/").rstrip("/")
    return text.rsplit("/", 1)[-1] or None


def _v1_status_payload() -> dict[str, Any]:
    raw_status = player.status()
    loop_status = loop_player.status()
    return {
        "running": bool(raw_status.get("running")),
        "paused": bool(raw_status.get("paused")),
        "session": _v1_session_basename(raw_status.get("session")),
        "playlist_size": playlist.size(),
        "loop": {
            "enabled": bool(loop_status.get("enabled")),
            "playing": bool(loop_status.get("playing")),
            "suppressed": bool(loop_status.get("suppressed")),
        },
    }


def _v1_sessions_payload() -> dict[str, Any]:
    categories_data = _load_session_categories()
    mapping = categories_data["sessions"]
    sessions = [
        {"name": name, "category": mapping.get(name)}
        for name in _list_session_names()
    ]
    return {"sessions": sessions, "categories": categories_data["categories"]}


def _v1_inspect_session_payload(session_name: str) -> dict[str, Any]:
    inspection = SessionCatalog(DATA_DIR).inspect(session_name)
    return {
        "name": inspection.name,
        "playable": inspection.valid,
        "issues": list(inspection.issues),
        "files": {
            "json_count": len(inspection.json_files),
            "mp3_count": len(inspection.mp3_files),
        },
    }


def _v1_playlist_item(entry: Any) -> Optional[dict[str, Any]]:
    if not isinstance(entry, dict):
        return None
    item: dict[str, Any] = {}
    for key in ("id", "session", "retries", "category", "pending", "transitioning"):
        if key in entry:
            item[key] = entry[key]
    return item or None


def _v1_playlist_payload(limit: int) -> dict[str, Any]:
    categories_data = _load_session_categories()
    mapping = categories_data["sessions"]
    current = _enrich_entry_with_category(_get_current_entry(), mapping)
    queue = _enrich_queue_with_categories(playlist.snapshot(), mapping)
    return {
        "current": _v1_playlist_item(current),
        "queue": [
            item
            for item in (_v1_playlist_item(entry) for entry in queue[:limit])
            if item is not None
        ],
        "queue_size": len(queue),
    }


v1_api = create_v1_blueprint(
    V1Context(
        get_status=_v1_status_payload,
        list_sessions=_v1_sessions_payload,
        inspect_session=_v1_inspect_session_payload,
        get_playlist=_v1_playlist_payload,
    )
)

bluetooth_api = create_bluetooth_blueprint(
    BluetoothUiContext(
        scan=_bt_ui_scan,
        pair=_bt_ui_pair,
        trust=_bt_ui_trust,
        connect=_bt_ui_connect,
        select_output=_bt_ui_select_output,
        test_audio=_bt_ui_test_audio,
        refresh_state=_bt_ui_state,
    )
)


app.register_blueprint(legacy_api)
app.register_blueprint(bluetooth_api, url_prefix="/bluetooth")
app.register_blueprint(v1_api, url_prefix="/api/v1")


def main() -> None:
    """Explicit production entry point; imports never launch hardware."""
    print("Servo Sync Player - Web Interface")
    print(f"Logs directory: {servo_logger.log_dir}")
    print(f"Current log file: {servo_logger.get_latest_log_file()}")
    print("Available endpoints:")
    print("  - Main interface: http://localhost:5000")
    print("  - /logs        : Get recent log lines (JSON)")
    print("  - /logs/stream : Real-time log stream")
    print("  - /logs/stats  : Session statistics")
    print("  - /logs/download : Download log file")
    initialize_runtime(acquire_process_lock=True)
    _install_shutdown_handlers()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
