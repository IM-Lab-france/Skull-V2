from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path

import pytest


def load_gunicorn_config() -> dict[str, object]:
    root = Path(__file__).parents[2]
    return runpy.run_path(str(root / "gunicorn.conf.py"))


def test_wsgi_config_is_single_worker_without_preload() -> None:
    config = load_gunicorn_config()

    assert config["workers"] == 1
    assert config["threads"] == 1
    assert config["worker_class"] == "sync"
    assert config["preload_app"] is False
    assert config["timeout"] == 30
    assert config["graceful_timeout"] == 10


def test_wsgi_entry_imports_without_hardware_in_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    monkeypatch.delitem(sys.modules, "web_app", raising=False)
    monkeypatch.delitem(sys.modules, "wsgi_entry", raising=False)

    import wsgi_entry

    response = wsgi_entry.app.test_client().get("/health/live")
    assert response.status_code == 200
    assert response.get_json()["mode"] == "simulated"
    response = wsgi_entry.app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["checks"]["runtime_initialized"] is False


def test_wsgi_hooks_initialize_real_worker_and_cleanup_once_per_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    fake_web_app = types.SimpleNamespace(
        initialize_runtime=lambda **kwargs: calls.append(("init", kwargs)),
        cleanup_runtime=lambda: calls.append(("cleanup", None)),
    )
    monkeypatch.setitem(sys.modules, "web_app", fake_web_app)
    monkeypatch.delenv("SKULL_HARDWARE_MODE", raising=False)
    config = load_gunicorn_config()

    config["post_worker_init"](object())
    config["worker_int"](object())
    config["worker_exit"](object(), object())

    assert calls == [
        ("init", {"acquire_process_lock": True}),
        ("cleanup", None),
        ("cleanup", None),
    ]


def test_local_launcher_uses_locked_single_worker_configuration() -> None:
    root = Path(__file__).parents[2]
    launcher = (root / "launch_wsgi.sh").read_text(encoding="utf-8")
    config = (root / "gunicorn.conf.py").read_text(encoding="utf-8")

    assert "--config" in launcher
    assert "wsgi_entry:app" in launcher
    assert "SKULL_HARDWARE_MODE" in launcher
    assert "workers = 1" in config
    assert "threads = 1" in config
    assert "preload_app = False" in config
