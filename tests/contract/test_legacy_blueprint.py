from __future__ import annotations

from pathlib import Path

import pytest

from tests.contract.test_http_legacy_contracts import load_app


def _non_static_rules(
    app, endpoint_prefix: str | None = None
) -> set[tuple[str, tuple[str, ...]]]:
    rules: set[tuple[str, tuple[str, ...]]] = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("static."):
            continue
        if endpoint_prefix is not None and not rule.endpoint.startswith(endpoint_prefix):
            continue
        methods = tuple(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        rules.add((rule.rule, methods))
    return rules


def test_all_public_routes_are_registered_by_the_legacy_blueprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = load_app(tmp_path, monkeypatch)
    routes = [
        rule
        for rule in api.app.url_map.iter_rules()
        if rule.endpoint.startswith("legacy.")
    ]

    assert routes
    assert len(routes) == len(
        [
            rule
            for rule in api.app.url_map.iter_rules()
            if rule.endpoint != "static" and not rule.endpoint.startswith("static.")
            and not rule.endpoint.startswith("v1.")
            and not rule.endpoint.startswith("bluetooth.")
        ]
    )
    assert api.legacy_api.name == "legacy"


def test_legacy_route_matrix_is_stable_after_blueprint_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = load_app(tmp_path, monkeypatch)
    expected = {
        ("/", ("GET",)),
        ("/api/enqueue", ("POST",)),
        ("/api/sessions", ("GET",)),
        ("/pause", ("POST",)),
        ("/play", ("POST",)),
        ("/resume", ("POST",)),
        ("/status", ("GET",)),
        ("/stop", ("POST",)),
        ("/scan", ("POST",)),
        ("/pair", ("POST",)),
        ("/playlist", ("GET", "POST")),
        ("/playlist/skip", ("POST",)),
        ("/esp32/status", ("GET",)),
    }
    assert expected <= _non_static_rules(api.app)


def test_blueprint_reload_creates_no_duplicate_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = load_app(first_dir, monkeypatch)
    first_count = len(_non_static_rules(first.app, "legacy."))
    second = load_app(second_dir, monkeypatch)
    second_count = len(_non_static_rules(second.app, "legacy."))
    assert first_count == second_count
