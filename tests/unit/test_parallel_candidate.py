from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from tests.contract.test_http_legacy_contracts import assert_contract, load_app


ROOT = Path(__file__).parents[2]
SNAPSHOTS = json.loads(
    (ROOT / "tests" / "contract" / "http_legacy_snapshots.json").read_text(
        encoding="utf-8"
    )
)


def _load_gunicorn_config():
    spec = importlib.util.spec_from_file_location(
        "skull_candidate_gunicorn_config", ROOT / "gunicorn.conf.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_unit_is_parallel_and_not_auto_enabled() -> None:
    unit = (ROOT / "deploy" / "skull-candidate.service.example").read_text(
        encoding="utf-8"
    )
    assert "SKULL_HARDWARE_MODE=simulated" in unit
    assert "SKULL_WSGI_BIND=127.0.0.1:5002" in unit
    assert "ExecStart=" in unit
    assert not any(line.strip() == "[Install]" for line in unit.splitlines())
    assert "Restart=no" in unit


def test_candidate_gunicorn_uses_one_worker_and_loopback_port(monkeypatch) -> None:
    monkeypatch.delenv("SKULL_WSGI_BIND", raising=False)
    config = _load_gunicorn_config()
    assert config.bind == "127.0.0.1:5002"
    assert config.workers == 1
    assert config.threads == 1
    assert config.preload_app is False


def test_candidate_route_matrix_matches_frozen_legacy_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = load_app(tmp_path, monkeypatch)
    client = api.app.test_client()
    cases = (
        (client.get, "/status", "GET /status"),
        (client.get, "/api/sessions", "GET /api/sessions"),
        (lambda path: client.post(path, json={}), "/api/enqueue", "POST /api/enqueue invalid"),
        (
            lambda path: client.post(path, json={"session": "Accueil"}),
            "/api/enqueue",
            "POST /api/enqueue valid",
        ),
        (lambda path: client.post(path, json={}), "/play", "POST /play invalid"),
        (
            lambda path: client.post(path, json={"session": "Accueil"}),
            "/play",
            "POST /play valid",
        ),
        (client.post, "/pause", "POST /pause"),
        (client.post, "/resume", "POST /resume"),
        (client.post, "/stop", "POST /stop"),
        (client.get, "/playlist", "GET /playlist"),
        (lambda path: client.post(path, json={}), "/playlist", "POST /playlist invalid"),
        (
            lambda path: client.post(path, json={"session": "Accueil"}),
            "/playlist",
            "POST /playlist valid",
        ),
        (client.delete, "/playlist/999", "DELETE /playlist/999"),
        (
            lambda path: client.post(path, json={"direction": "sideways"}),
            "/playlist/999/move",
            "POST /playlist/999/move invalid",
        ),
        (client.post, "/playlist/skip", "POST /playlist/skip"),
        (client.get, "/categories", "GET /categories"),
        (lambda path: client.post(path, json={"name": "test"}), "/categories", "POST /categories"),
        (client.get, "/esp32/status", "GET /esp32/status"),
        (
            lambda path: client.post(path, json={"on": True}),
            "/esp32/relay",
            "POST /esp32/relay",
        ),
        (client.get, "/esp32/button-config", "GET /esp32/button-config"),
    )

    assert {name for _, _, name in cases} == set(SNAPSHOTS)
    for call, path, name in cases:
        response = call(path)
        body = assert_contract(response, name)
        assert response.content_type == "application/json"
        assert isinstance(body, dict)
