from __future__ import annotations

import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


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

    def load(self, session_dir: Path) -> None:
        self.state["session"] = session_dir.name

    def play(self) -> None:
        self.state["running"] = True

    def pause(self) -> None:
        self.state["paused"] = True

    def resume(self) -> None:
        self.state["paused"] = False

    def stop(self, *args, **kwargs) -> None:
        self.state["running"] = False


class FakeLoopPlayer:
    def __init__(self, *args, **kwargs) -> None:
        self.suppressed = False

    def suppress_for_session(self) -> None:
        self.suppressed = True

    def release_suppression(self, delay=0.0) -> None:
        self.suppressed = False

    def status(self) -> dict:
        return {"playing": False, "suppressed": self.suppressed}


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
    for name in ("Accueil", "Demo", "Autre"):
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
    return web_app


@pytest.fixture
def api(tmp_path, monkeypatch):
    return load_app(tmp_path, monkeypatch)


def reset_state(api) -> None:
    api.playlist.clear()
    api._set_current_entry(None)
    api.player.state.update({"running": False, "paused": False, "session": None})


def test_empty_queue_and_idle_enqueue_starts_immediately(api) -> None:
    reset_state(api)
    assert api.playlist.snapshot() == []
    api.playlist.add("Demo")
    api._ensure_playback_running()
    assert api.playlist.snapshot() == []
    assert api._get_current_entry()["session"] == "Demo"
    assert api.player.status()["running"] is True


def test_enqueue_while_playing_stays_queued(api) -> None:
    reset_state(api)
    api.playlist.add("Demo")
    api._ensure_playback_running()
    api.playlist.add("Autre")
    api._ensure_playback_running()
    assert api._get_current_entry()["session"] == "Demo"
    assert [item["session"] for item in api.playlist.snapshot()] == ["Autre"]


def test_normal_finish_starts_next_item(api, monkeypatch) -> None:
    reset_state(api)
    api.playlist.add("Demo")
    api._ensure_playback_running()
    api.playlist.add("Autre")

    class ImmediateThread:
        def __init__(self, target, daemon=True):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(api.threading, "Thread", ImmediateThread)
    api._handle_track_finished("completed", None, "Demo")
    assert api._get_current_entry()["session"] == "Autre"
    assert api.playlist.snapshot() == []


def test_skip_and_stop_clear_or_advance_as_current_reference(api, monkeypatch) -> None:
    reset_state(api)
    api._set_current_entry({"session": "Demo", "id": 1})
    api.player.state["running"] = True
    response = api.app.test_client().post("/playlist/skip")
    assert response.status_code == 200
    assert response.get_json() == {"status": "skipping"}

    api._set_current_entry({"session": "Demo", "id": 1})
    api.player.state["running"] = True
    response = api.app.test_client().post("/stop")
    assert response.status_code == 200
    assert response.get_json() == {"status": "stopped"}
    assert api._get_current_entry() is None


def test_delete_current_session_stops_and_removes_it(api) -> None:
    reset_state(api)
    api._set_current_entry({"session": "Demo", "id": 1})
    api.player.state["running"] = True
    response = api.app.test_client().delete("/sessions/Demo")
    assert response.status_code == 200
    assert response.get_json()["status"] == "deleted"
    assert api._get_current_entry() is None
    assert not (api.DATA_DIR / "Demo").exists()


def test_random_candidates_exclude_accueil(api) -> None:
    reset_state(api)
    candidates = api._eligible_random_sessions()
    assert "Accueil" not in candidates
    assert set(candidates) == {"Demo", "Autre"}


def test_concurrent_enqueue_keeps_unique_ordered_ids(api) -> None:
    reset_state(api)
    with ThreadPoolExecutor(max_workers=8) as pool:
        items = list(pool.map(api.playlist.add, ["Demo"] * 32))
    queued = api.playlist.snapshot()
    assert len(queued) == 32
    assert len({item["id"] for item in queued}) == 32
    assert [item["id"] for item in queued] == sorted(item["id"] for item in queued)
    assert {item["id"] for item, _ in items} == {item["id"] for item in queued}


def test_audio_error_before_start_does_not_set_current(api, monkeypatch) -> None:
    reset_state(api)

    def fail_load(session_dir):
        raise RuntimeError("synthetic audio failure")

    monkeypatch.setattr(api.player, "load", fail_load)
    assert api._start_session("Demo", "test") is False
    assert api._get_current_entry() is None
    assert api.player.status()["running"] is False


def test_bluetooth_error_before_start_does_not_set_current(api, monkeypatch) -> None:
    reset_state(api)
    monkeypatch.setattr(api, "BT_DEVICE_ADDR", "TEST-BLUETOOTH-ADDRESS")
    monkeypatch.setattr(api, "_ensure_bt_connection", lambda address: False)
    assert api._start_session("Demo", "test") is False
    assert api._get_current_entry() is None
    assert api.player.status()["running"] is False
