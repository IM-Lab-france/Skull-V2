"""Public playlist launcher that lists available sessions and forwards play requests."""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

import requests
from flask import Flask, jsonify, render_template, request, Response

CLIENT_COOKIE_NAME = "playlist_public_id"
DEFAULT_COOLDOWN_SECONDS = 180
MAX_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days

LIBRARY_ROOT = (
    Path(os.environ.get("PLAYLIST_LIBRARY_DIR", "data")).expanduser().resolve()
)
COOLDOWN_SECONDS = int(os.environ.get("PLAYLIST_COOLDOWN", DEFAULT_COOLDOWN_SECONDS))
FORWARD_TIMEOUT = float(os.environ.get("PLAYLIST_FORWARD_TIMEOUT", "10"))
STATUS_TIMEOUT = float(os.environ.get("PLAYLIST_STATUS_TIMEOUT", "6"))

HEADER_IMAGE_SRC = "/static/web.png"
HEADER_IMAGE_CLASS = "fixed-header-image"
HEADER_IMAGE_STYLE = (
    "<style>"
    ".fixed-header-image{position:fixed;top:0;left:50%;transform:translateX(-50%);"
    "z-index:1000;pointer-events:none;max-width:100%;height:auto;}"
    "</style>"
)
_BODY_TAG_RE = re.compile(r"<body([^>]*)>", re.IGNORECASE)


def _backend_base_url() -> str:
    base = os.environ.get("PLAYLIST_BACKEND_BASE")
    if base:
        return base.rstrip("/")
    host = request.host.split(":")[0]
    return f"http://{host}:5000"


app = Flask(__name__, static_folder="static", template_folder="templates")


class ClientState:
    __slots__ = ("created_at", "last_submit_at")

    def __init__(self, created_at: float) -> None:
        self.created_at = created_at
        self.last_submit_at = 0.0


_clients: Dict[str, ClientState] = {}
_client_lock = threading.Lock()


def _scan_available_sessions() -> list[dict[str, str]]:
    sessions: list[dict[str, str]] = []
    base = LIBRARY_ROOT
    if not base.exists():
        return sessions
    try:
        for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir():
                sessions.append({"name": entry.name, "display": entry.name})
    except Exception:
        pass
    return sessions


def _fetch_playlist_state() -> dict:
    try:
        response = requests.get(
            f"{_backend_base_url()}/playlist", timeout=STATUS_TIMEOUT
        )
        if response.ok:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}
        return {"error": response.text, "status": response.status_code}
    except Exception as exc:
        return {"error": str(exc)}


def _resolve_client() -> tuple[str, bool]:
    raw_id = request.cookies.get(CLIENT_COOKIE_NAME)
    created = False
    if raw_id:
        try:
            uuid.UUID(raw_id)
            client_id = raw_id
        except Exception:
            client_id = uuid.uuid4().hex
            created = True
    else:
        client_id = uuid.uuid4().hex
        created = True

    with _client_lock:
        if client_id not in _clients:
            _clients[client_id] = ClientState(created_at=time.time())
            created = True
    return client_id, created


def _client_state(client_id: str) -> ClientState:
    with _client_lock:
        return _clients.setdefault(client_id, ClientState(created_at=time.time()))


def _cooldown_remaining(state: ClientState) -> float:
    elapsed = time.time() - state.last_submit_at
    remaining = COOLDOWN_SECONDS - elapsed
    return max(0.0, remaining)


def _json(
    payload: dict,
    status: int = 200,
    client_id: str | None = None,
    set_cookie: bool = False,
) -> Response:
    resp = jsonify(payload)
    resp.status_code = status
    if set_cookie and client_id:
        resp.set_cookie(
            CLIENT_COOKIE_NAME,
            client_id,
            max_age=MAX_COOKIE_AGE,
            httponly=True,
            samesite="Lax",
        )
    return resp


def _inject_header_image(html: str) -> str:
    if HEADER_IMAGE_CLASS in html:
        return html
    updated = html
    if "</head>" in updated:
        updated = updated.replace("</head>", HEADER_IMAGE_STYLE + "</head>", 1)
    match = _BODY_TAG_RE.search(updated)
    if match:
        start, end = match.span()
        body_tag = match.group(0)
        injection = (
            f"{body_tag}<img src=\"{HEADER_IMAGE_SRC}\" alt=\"Page overlay\" "
            f"class=\"{HEADER_IMAGE_CLASS}\">"
        )
        updated = updated[:start] + injection + updated[end:]
    return updated


@app.route("/favicon.ico")
def favicon() -> Response:
    return app.send_static_file("SkullPlayer.png")


@app.route("/")
def index() -> Response:
    client_id, created = _resolve_client()
    state = _client_state(client_id)
    cooldown = int(_cooldown_remaining(state))
    html = render_template(
        "playlist_only.html",
        cooldown=COOLDOWN_SECONDS,
        cooldown_remaining=cooldown,
        available_sessions=_scan_available_sessions(),
        playlist_state=_fetch_playlist_state(),
    )
    html = _inject_header_image(html)
    resp = app.make_response(html)
    if created:
        resp.set_cookie(
            CLIENT_COOKIE_NAME,
            client_id,
            max_age=MAX_COOKIE_AGE,
            httponly=True,
            samesite="Lax",
        )
    return resp


@app.route("/api/sessions")
def api_sessions() -> Response:
    client_id, created = _resolve_client()
    state = _client_state(client_id)
    payload = {
        "client_id": client_id,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "cooldown_remaining": int(_cooldown_remaining(state)),
        "sessions": _scan_available_sessions(),
        "playlist": _fetch_playlist_state(),
    }
    return _json(payload, client_id=client_id, set_cookie=created)


@app.route("/api/enqueue", methods=["POST"])
def api_enqueue() -> Response:
    client_id, created = _resolve_client()
    state = _client_state(client_id)

    remaining = _cooldown_remaining(state)
    if remaining > 0:
        return _json(
            {
                "error": "Cooldown actif",
                "cooldown_remaining": int(remaining),
            },
            status=429,
            client_id=client_id,
            set_cookie=created,
        )

    data = request.get_json(silent=True) or {}
    session = (data.get("session") or "").strip()
    if not session:
        return _json(
            {"error": "Le champ 'session' est requis"},
            status=400,
            client_id=client_id,
            set_cookie=created,
        )

    available = {entry["name"] for entry in _scan_available_sessions()}
    if session not in available:
        return _json(
            {"error": "Session inconnue"},
            status=404,
            client_id=client_id,
            set_cookie=created,
        )

    try:
        upstream = requests.post(
            f"{_backend_base_url()}/play", json={"session": session},
            timeout=FORWARD_TIMEOUT,
        )
    except requests.RequestException as exc:
        return _json(
            {"error": f"Serveur principal indisponible: {exc}"},
            status=502,
            client_id=client_id,
            set_cookie=created,
        )

    try:
        upstream_payload = upstream.json()
    except ValueError:
        upstream_payload = {"status": upstream.text.strip()}

    if not upstream.ok:
        message = (
            upstream_payload.get("error")
            or upstream_payload.get("status")
            or "Echec serveur"
        )
        return _json(
            {"error": message, "server": upstream_payload},
            status=upstream.status_code,
            client_id=client_id,
            set_cookie=created,
        )

    state.last_submit_at = time.time()
    payload = {
        "status": upstream_payload.get("status", "queued"),
        "server": upstream_payload,
        "cooldown_remaining": COOLDOWN_SECONDS,
        "playlist": _fetch_playlist_state(),
    }
    return _json(
        payload, status=upstream.status_code, client_id=client_id, set_cookie=created
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
