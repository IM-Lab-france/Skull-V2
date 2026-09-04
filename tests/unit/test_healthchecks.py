from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest


def fresh_web_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKULL_SMOKE_WEBHOOK_URL", "")
    monkeypatch.delitem(sys.modules, "web_app", raising=False)
    import web_app

    return web_app


def test_live_is_200_without_initializing_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = fresh_web_app(tmp_path, monkeypatch)
    api.initialize_runtime = lambda **kwargs: pytest.fail("live must not initialize runtime")

    response = api.app.test_client().get("/health/live")
    body = response.get_json()

    assert response.status_code == 200
    assert set(body) == {"status", "version", "mode", "checks"}
    assert body["status"] == "ok"
    assert body["checks"] == {"configuration": True, "process": True}
    assert api._runtime_initialized is False
    assert "/" not in json.dumps(body)


def test_ready_is_503_before_runtime_initialization_and_is_fast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = fresh_web_app(tmp_path, monkeypatch)
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    started = time.monotonic()

    response = api.app.test_client().get("/health/ready")
    elapsed = time.monotonic() - started
    body = response.get_json()

    assert response.status_code == 503
    assert elapsed < 1.0
    assert set(body) == {"status", "version", "mode", "checks"}
    assert body["status"] == "not_ready"
    assert body["mode"] == "simulated"
    assert body["checks"] == {
        "configuration": True,
        "runtime_initialized": False,
        "player": False,
        "loop_player": False,
    }


def test_ready_is_200_after_both_simulated_components_initialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = fresh_web_app(tmp_path, monkeypatch)
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")

    class FakePlayer:
        def set_on_track_finished(self, callback) -> None:
            self.callback = callback

    class FakeLoopPlayer:
        def __init__(self, _storage_dir) -> None:
            pass

        def stop(self) -> None:
            pass

    api.initialize_runtime(
        sync_player_cls=FakePlayer,
        loop_player_cls=FakeLoopPlayer,
    )
    response = api.app.test_client().get("/health/ready")
    body = response.get_json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["mode"] == "simulated"
    assert body["checks"] == {
        "configuration": True,
        "runtime_initialized": True,
        "player": True,
        "loop_player": True,
    }
    api.cleanup_runtime()


def test_ready_is_503_for_invalid_configuration_or_missing_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = fresh_web_app(tmp_path, monkeypatch)
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "invalid")
    response = api.app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["mode"] is None
    assert response.get_json()["checks"]["configuration"] is False

    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    api._runtime_initialized = True
    api._runtime_player = object()
    api._runtime_loop_player = None
    response = api.app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["checks"]["player"] is True
    assert response.get_json()["checks"]["loop_player"] is False
