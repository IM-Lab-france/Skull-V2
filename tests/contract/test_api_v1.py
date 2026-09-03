from __future__ import annotations

from flask import Flask

from api.v1 import V1Context, create_v1_blueprint
from domain.errors import InvalidInputError, NotFoundError
from tests.contract.test_http_legacy_contracts import load_app


def _v1_test_app(context: V1Context) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(create_v1_blueprint(context), url_prefix="/api/v1")
    return app


def test_every_v1_route_uses_the_success_envelope() -> None:
    context = V1Context(
        get_status=lambda: {"running": False},
        list_sessions=lambda: {"sessions": [], "categories": []},
        inspect_session=lambda name: {"name": name, "playable": True},
        get_playlist=lambda limit: {"current": None, "queue": [], "queue_size": 0},
    )
    client = _v1_test_app(context).test_client()

    responses = [
        client.get("/api/v1/status"),
        client.get("/api/v1/sessions"),
        client.get("/api/v1/sessions/Accueil"),
        client.get("/api/v1/playlist"),
        client.get("/api/v1/playlist?limit=1"),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(response.content_type == "application/json" for response in responses)
    assert all(response.get_json()["ok"] is True for response in responses)
    assert all("data" in response.get_json() for response in responses)


def test_v1_validates_inputs_before_calling_business_context() -> None:
    calls: list[str] = []

    def inspect(name: str):
        calls.append(name)
        return {"name": name}

    def playlist(limit: int):
        calls.append(str(limit))
        return {"queue": []}

    context = V1Context(
        get_status=lambda: {},
        list_sessions=lambda: {},
        inspect_session=inspect,
        get_playlist=playlist,
    )
    client = _v1_test_app(context).test_client()

    invalid_session = client.get("/api/v1/sessions/a/b")
    invalid_limit = client.get("/api/v1/playlist?limit=0")
    non_numeric_limit = client.get("/api/v1/playlist?limit=abc")

    assert invalid_session.status_code == 400
    assert invalid_limit.status_code == 400
    assert non_numeric_limit.status_code == 400
    expected_error = {
        "ok": False,
        "error": {"code": "invalid_input", "message": "Entree invalide"},
    }
    assert all(response.get_json() == expected_error
               for response in (invalid_session, invalid_limit, non_numeric_limit))
    assert calls == []


def test_v1_maps_domain_errors_without_reflecting_details() -> None:
    context = V1Context(
        get_status=lambda: (_ for _ in ()).throw(
            RuntimeError("SECRET path=/srv/skull command=bluetoothctl")
        ),
        list_sessions=lambda: (_ for _ in ()).throw(NotFoundError("/srv/skull")),
        inspect_session=lambda name: (_ for _ in ()).throw(
            InvalidInputError("/srv/skull/secret")
        ),
        get_playlist=lambda limit: {"path": "/srv/skull", "secret": "hidden"},
    )
    client = _v1_test_app(context).test_client()

    internal = client.get("/api/v1/status")
    not_found = client.get("/api/v1/sessions")
    invalid = client.get("/api/v1/sessions/Accueil")
    sanitized = client.get("/api/v1/playlist")

    assert internal.status_code == 500
    assert not_found.status_code == 404
    assert invalid.status_code == 400
    assert sanitized.status_code == 200
    for response in (internal, not_found, invalid, sanitized):
        body = response.get_data(as_text=True)
        assert "SECRET" not in body
        assert "/srv/skull" not in body
        assert "bluetoothctl" not in body


def test_v1_coexists_with_the_unchanged_legacy_surface(
    tmp_path, monkeypatch
) -> None:
    api = load_app(tmp_path, monkeypatch)
    client = api.app.test_client()

    legacy = client.get("/status")
    versioned = client.get("/api/v1/status")

    assert legacy.status_code == 200
    assert versioned.status_code == 200
    assert legacy.get_json()["running"] is False
    assert versioned.get_json()["ok"] is True
    assert versioned.get_json()["data"]["running"] is False
    assert any(
        rule.rule == "/status" and rule.endpoint.startswith("legacy.")
        for rule in api.app.url_map.iter_rules()
    )
    assert any(
        rule.rule == "/api/v1/status" and rule.endpoint.startswith("v1.")
        for rule in api.app.url_map.iter_rules()
    )
