from __future__ import annotations

import subprocess
import sys
import types
import socket
import time
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

from services.esp32_supervisor import ESP32Supervisor


class FakeLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakePlayer:
    def __init__(self) -> None:
        self.hw = types.SimpleNamespace(SPECS={})
        self.state = {"running": False, "session": None}

    def set_on_track_finished(self, callback) -> None:
        self.callback = callback

    def load(self, session_dir: Path) -> None:
        self.state["session"] = session_dir.name

    def play(self) -> None:
        self.state["running"] = True

    def status(self) -> dict:
        return dict(self.state)


class FakeLoopPlayer:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def suppress_for_session(self) -> None:
        pass

    def release_suppression(self, delay=0.0) -> None:
        pass

    def status(self) -> dict:
        return {"playing": False}


class WebhookHandler(BaseHTTPRequestHandler):
    calls: list[dict[str, object]] = []
    response_code = 200

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.__class__.calls.append({"method": "POST", "path": self.path})
        self.send_response(self.__class__.response_code)
        self.end_headers()

    def log_message(self, format, *args) -> None:
        pass


class SilentHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        time.sleep(0.3)

    def log_message(self, format, *args) -> None:
        pass


def load_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_sync = types.ModuleType("sync_player")
    fake_sync.SyncPlayer = FakePlayer
    fake_loop = types.ModuleType("loop_player")
    fake_loop.LoopPlayer = FakeLoopPlayer
    fake_logger = types.ModuleType("logger")
    fake_logger.servo_logger = types.SimpleNamespace(logger=FakeLogger())
    for name, module in {
        "sync_player": fake_sync,
        "loop_player": fake_loop,
        "logger": fake_logger,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKULL_SMOKE_WEBHOOK_URL", "")
    sys.modules.pop("web_app", None)
    import web_app

    web_app.DATA_DIR = tmp_path / "data"
    web_app.DATA_DIR.mkdir(exist_ok=True)
    for name in ("Accueil", "Demo"):
        session = web_app.DATA_DIR / name
        session.mkdir()
        (session / "scene.mp3").write_bytes(b"synthetic")
        (session / "scene.json").write_text("{}", encoding="utf-8")

    web_app._ensure_session_exists = lambda name: web_app.DATA_DIR / name
    web_app.BT_DEVICE_ADDR = ""
    return web_app


@pytest.fixture
def api(tmp_path, monkeypatch):
    return load_app(tmp_path, monkeypatch)


@pytest.fixture
def webhook_server():
    WebhookHandler.calls = []
    WebhookHandler.response_code = 200
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/smoke", WebhookHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def silent_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SilentHandler)
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def fake_curl(api, monkeypatch, *, mode="real") -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def run(command, **kwargs):
        calls.append({"command": command, "timeout": kwargs.get("timeout")})
        if mode == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        if mode == "refused":
            raise ConnectionError("synthetic connection refused")
        if mode == "failed":
            return subprocess.CompletedProcess(command, 22, stdout=b"", stderr=b"synthetic failure")

        request = Request(command[-1], data=b"", method="POST")
        with urlopen(request, timeout=kwargs["timeout"]):
            pass
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(api.subprocess, "run", run)
    return calls


def test_status_does_not_run_synchronous_bluetooth_reconnect(
    api, monkeypatch
) -> None:
    api.BT_DEVICE_ADDR = "AA:BB:CC:DD:EE:FF"
    monkeypatch.setattr(
        api,
        "_bluetooth_info",
        lambda _address: {
            "paired": True,
            "trusted": True,
            "connected": False,
            "audio_sink_capable": False,
        },
    )
    monkeypatch.setattr(api._PULSEAUDIO_OUTPUT_ADAPTER, "selected_for", lambda _address: None)
    monkeypatch.setattr(
        api,
        "_ensure_bt_connection",
        lambda *_args, **_kwargs: pytest.fail("/status must not reconnect Bluetooth"),
    )
    api._bt_reconnect_worker = types.SimpleNamespace(
        last_result=None,
        last_attempt_ts=0.0,
        busy=True,
    )
    monkeypatch.setattr(api, "_start_bt_reconnect_worker", lambda _address: None)
    api.initialize_runtime(
        sync_player_cls=FakePlayer,
        loop_player_cls=FakeLoopPlayer,
    )
    monkeypatch.setattr(
        api,
        "_bluetooth_info",
        lambda _address: pytest.fail("/status must not wait on BlueZ"),
    )
    monkeypatch.setattr(
        api._PULSEAUDIO_OUTPUT_ADAPTER,
        "selected_for",
        lambda _address: pytest.fail("/status must not wait on PulseAudio"),
    )

    response = api.app.test_client().get("/status")

    assert response.status_code == 200
    assert response.get_json()["bluetooth"]["connected"] is None
    assert response.get_json()["bluetooth"]["connection_state"] == "reconnecting"


def test_bt_reconnect_propagates_controller_timeout(api, monkeypatch) -> None:
    calls: list[tuple[str, float]] = []

    def fake_connect(address: str, *, timeout_s: float | None = None):
        calls.append((address, float(timeout_s)))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(api, "_bluetoothctl_connect", fake_connect)
    monkeypatch.setattr(api, "_wait_bt_flag", lambda *args, **kwargs: True)

    assert api._connect_bt_once("AA:BB:CC:DD:EE:FF", 2.5) is True
    assert calls == [("AA:BB:CC:DD:EE:FF", 2.5)]


def test_webhook_is_posted_only_for_accueil_and_after_play(api, monkeypatch, webhook_server) -> None:
    url, handler = webhook_server
    api.ACCUEIL_WEBHOOK_URL = url
    calls = fake_curl(api, monkeypatch)

    assert api._start_session("Demo", "test") is True
    assert handler.calls == []
    assert api._start_session("aCcUeIl", "test") is True
    assert handler.calls == [{"method": "POST", "path": "/smoke"}]
    assert calls[0]["command"][:4] == ["curl", "-sS", "-X", "POST"]
    assert api.player.status()["running"] is True


@pytest.mark.parametrize("mode", ["timeout", "refused", "failed"])
def test_webhook_failures_do_not_cancel_playback(api, monkeypatch, webhook_server, mode) -> None:
    url, handler = webhook_server
    if mode == "failed":
        handler.response_code = 500
    api.ACCUEIL_WEBHOOK_URL = url
    calls = fake_curl(api, monkeypatch, mode=mode)
    assert api._start_session("Accueil", "test") is True
    assert api._get_current_entry()["session"] == "Accueil"
    assert api.player.status()["running"] is True
    assert calls[0]["timeout"] == api.ACCUEIL_WEBHOOK_TIMEOUT


def test_webhook_url_is_redacted_from_diagnostics(api, monkeypatch) -> None:
    secret_url = "https://hooks.example.test/notify?token=synthetic-secret"
    messages: list[str] = []

    class CaptureLogger:
        def __getattr__(self, name):
            def capture(*args, **kwargs):
                messages.append(" ".join(str(item) for item in args))

            return capture

    api.servo_logger.logger = CaptureLogger()
    api.ACCUEIL_WEBHOOK_URL = secret_url

    def missing_curl(*args, **kwargs):
        raise FileNotFoundError(secret_url)

    monkeypatch.setattr(api.subprocess, "run", missing_curl)
    assert api._start_session("Accueil", "test") is True

    assert secret_url not in " ".join(messages)
    assert "<redacted-webhook-url>" in " ".join(messages)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


@pytest.mark.parametrize("failure", ["unavailable", "invalid_json"])
def test_esp32_unavailable_and_invalid_json_are_reported(api, monkeypatch, failure) -> None:
    api.load_esp32_config = lambda: {"host": "esp32.test", "port": 80, "enabled": True}

    if failure == "unavailable":
        def fake_urlopen(request, timeout):
            raise URLError(socket.gaierror(-2, "synthetic DNS failure"))
    else:
        def fake_urlopen(request, timeout):
            return FakeResponse(b"not-json")

    monkeypatch.setattr(api, "urlopen", fake_urlopen)
    response = api.app.test_client().post("/esp32/status/check")
    assert response.status_code == 200
    body = response.get_json()
    assert body["reachable"] is False
    assert body["reason"] == "network"
    assert isinstance(body["error"], str)


def test_esp32_silent_server_is_reported_as_controlled_network_error(
    api, monkeypatch, silent_server
) -> None:
    api.load_esp32_config = lambda: {
        "host": "127.0.0.1",
        "port": silent_server,
        "enabled": True,
    }
    monkeypatch.setattr(api, "ESP32_HTTP_TIMEOUT", 0.05)

    response = api.app.test_client().post("/esp32/status/check")
    assert response.status_code == 200
    body = response.get_json()
    assert body["reachable"] is False
    assert body["reason"] == "network"
    assert "127.0.0.1" not in body["error"]


def test_esp32_status_reads_supervisor_cache_without_network_call(api, monkeypatch) -> None:
    api.load_esp32_config = lambda: {
        "host": "esp32.test",
        "port": 80,
        "enabled": True,
    }
    supervisor = ESP32Supervisor(probe=lambda: {"relay": True}, enabled=lambda: True)
    supervisor._probe_once("automatic")
    api._esp32_supervisor = supervisor
    monkeypatch.setattr(
        api,
        "_esp32_request",
        lambda *args, **kwargs: pytest.fail("GET /esp32/status must use the cache"),
    )

    response = api.app.test_client().get("/esp32/status")

    assert response.status_code == 200
    body = response.get_json()
    assert body["reachable"] is True
    assert body["status"] == {"relay": True}
    assert body["supervision"]["state"] == "online"
    assert body["supervision"]["source"] == "automatic"
