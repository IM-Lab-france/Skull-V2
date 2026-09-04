from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest


SNAPSHOTS = json.loads(
    (Path(__file__).with_name("http_legacy_snapshots.json")).read_text(encoding="utf-8")
)


class FakeLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakePlayer:
    def __init__(self) -> None:
        self.hw = types.SimpleNamespace(SPECS={})
        self.state = {"running": False, "paused": False, "session": None}

    def set_on_track_finished(self, callback) -> None:
        self.callback = callback

    def status(self) -> dict:
        return dict(self.state)

    def pause(self) -> None:
        self.state["paused"] = True

    def resume(self) -> None:
        self.state["paused"] = False

    def stop(self, *args, **kwargs) -> None:
        self.state["running"] = False

    def set_channels(self, channels) -> None:
        self.channels = channels


class FakeLoopPlayer:
    def __init__(self, *args, **kwargs) -> None:
        self.state = {"enabled": False, "playing": False, "volume": 80}

    def status(self) -> dict:
        return dict(self.state)


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
    for name in ("Accueil", "Démo Été"):
        session = web_app.DATA_DIR / name
        session.mkdir()
        (session / "scene.mp3").write_bytes(b"synthetic")
        (session / "scene.json").write_text("{}", encoding="utf-8")

    def ensure_session(name: str):
        candidate = (web_app.DATA_DIR / name).resolve()
        if candidate.parent != web_app.DATA_DIR.resolve() or not candidate.is_dir():
            raise ValueError(f"Session introuvable: {name}")
        return candidate

    web_app._ensure_session_exists = ensure_session
    web_app._ensure_playback_running = lambda: None
    web_app._enqueue_or_play_session = lambda session, source, **kwargs: (
        {"status": "started", "session": session},
        200,
    )
    web_app.load_esp32_config = lambda: {
        "host": "esp32.test",
        "port": 80,
        "enabled": True,
    }
    web_app._esp32_request = lambda path, **kwargs: (
        {"state": "ok"} if path == "/api/status" else {"ok": True}
    )
    return web_app


@pytest.fixture
def api(tmp_path, monkeypatch):
    return load_app(tmp_path, monkeypatch)


def assert_contract(response, name: str) -> dict:
    spec = SNAPSHOTS[name]
    assert response.status_code == spec["status"]
    assert response.content_type == "application/json"
    body = response.get_json()
    assert isinstance(body, dict)
    type_checks = {
        "bool": lambda value: isinstance(value, bool),
        "int": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "str": lambda value: isinstance(value, str),
        "list": lambda value: isinstance(value, list),
        "object": lambda value: isinstance(value, dict),
        "nullable_object": lambda value: value is None or isinstance(value, dict),
    }
    for key, type_name in spec["required"].items():
        assert key in body
        assert type_checks[type_name](body[key]), f"{name}: {key} n'est pas {type_name}"
    return body


def test_status_and_sessions_contracts(api) -> None:
    client = api.app.test_client()
    assert_contract(client.get("/status"), "GET /status")
    body = assert_contract(client.get("/api/sessions"), "GET /api/sessions")
    assert set(body["playlist"]) >= {"current", "queue"}


def test_legacy_play_and_enqueue_contracts(api) -> None:
    client = api.app.test_client()
    assert_contract(client.post("/api/enqueue", json={}), "POST /api/enqueue invalid")
    assert_contract(
        client.post("/api/enqueue", json={"session": "Accueil"}),
        "POST /api/enqueue valid",
    )
    assert_contract(client.post("/play", json={}), "POST /play invalid")
    assert_contract(client.post("/play", json={"session": "Accueil"}), "POST /play valid")


def test_playback_control_contracts(api) -> None:
    client = api.app.test_client()
    for method, path, name in (
        (client.post, "/pause", "POST /pause"),
        (client.post, "/resume", "POST /resume"),
        (client.post, "/stop", "POST /stop"),
    ):
        assert_contract(method(path), name)


def test_playlist_contracts(api) -> None:
    client = api.app.test_client()
    assert_contract(client.get("/playlist"), "GET /playlist")
    assert_contract(client.post("/playlist", json={}), "POST /playlist invalid")
    assert_contract(
        client.post("/playlist", json={"session": "Accueil"}),
        "POST /playlist valid",
    )
    assert_contract(client.delete("/playlist/999"), "DELETE /playlist/999")
    assert_contract(
        client.post("/playlist/999/move", json={"direction": "sideways"}),
        "POST /playlist/999/move invalid",
    )
    assert_contract(client.post("/playlist/skip"), "POST /playlist/skip")


def test_categories_and_esp32_adapter_contracts(api) -> None:
    client = api.app.test_client()
    assert_contract(client.get("/categories"), "GET /categories")
    assert_contract(client.post("/categories", json={"name": "test"}), "POST /categories")
    assert_contract(client.get("/esp32/status"), "GET /esp32/status")
    assert_contract(client.post("/esp32/relay", json={"on": True}), "POST /esp32/relay")
    assert_contract(client.get("/esp32/button-config"), "GET /esp32/button-config")
