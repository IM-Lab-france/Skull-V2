"""Versioned, read-only HTTP contract for the Skull application.

The v1 surface is intentionally limited to observations during the
refactoring phase. Playback, Bluetooth, relay, upload and configuration
commands remain legacy-only until their security and migration tasks are
completed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Mapping

from flask import Blueprint, jsonify, request

from domain.errors import (
    ConflictError,
    DependencyUnavailableError,
    DomainError,
    InvalidInputError,
    NotFoundError,
    OperationNotAllowedError,
)


MAX_SESSION_NAME_LENGTH = 128
MAX_PLAYLIST_LIMIT = 100
_DECIMAL_RE = re.compile(r"^[0-9]+$")
_PRIVATE_KEYS = {
    "address",
    "cmd",
    "command",
    "error_detail",
    "file",
    "filename",
    "mac",
    "path",
    "password",
    "raw",
    "secret",
    "stderr",
    "stdout",
    "token",
    "traceback",
    "webhook",
}


@dataclass(frozen=True, slots=True)
class V1Context:
    """Read-only application callbacks injected at blueprint assembly time."""

    get_status: Callable[[], Mapping[str, Any]]
    list_sessions: Callable[[], Mapping[str, Any]]
    inspect_session: Callable[[str], Mapping[str, Any]]
    get_playlist: Callable[[int], Mapping[str, Any]]


def _public_value(value: Any) -> Any:
    """Keep response values JSON-safe and drop known sensitive fields."""
    if isinstance(value, Mapping):
        return {
            str(key): _public_value(item)
            for key, item in value.items()
            if str(key).lower() not in _PRIVATE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return None


def _success(data: Mapping[str, Any], status_code: int = 200):
    return jsonify({"ok": True, "data": _public_value(data)}), status_code


def _error(code: str, message: str, status_code: int):
    return (
        jsonify(
            {
                "ok": False,
                "error": {"code": code, "message": message},
            }
        ),
        status_code,
    )


def _invoke(callback: Callable[[], Mapping[str, Any]]):
    """Invoke a context callback without reflecting internal error details."""
    try:
        return _success(callback())
    except NotFoundError:
        return _error("not_found", "Ressource introuvable", 404)
    except InvalidInputError:
        return _error("invalid_input", "Entree invalide", 400)
    except ConflictError:
        return _error("conflict", "Conflit de ressource", 409)
    except OperationNotAllowedError:
        return _error("operation_not_allowed", "Operation non autorisee", 403)
    except DependencyUnavailableError:
        return _error("dependency_unavailable", "Dependance indisponible", 503)
    except DomainError:
        return _error("domain_error", "Operation impossible", 422)
    except Exception:
        return _error("internal_error", "Erreur interne", 500)


def _validated_limit() -> int | None:
    raw_value = request.args.get("limit")
    if raw_value is None:
        return None
    if not _DECIMAL_RE.fullmatch(raw_value):
        raise InvalidInputError("Limit invalide")
    limit = int(raw_value)
    if limit < 1 or limit > MAX_PLAYLIST_LIMIT:
        raise InvalidInputError("Limit invalide")
    return limit


def _validated_session_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_SESSION_NAME_LENGTH
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise InvalidInputError("Nom de session invalide")
    return value


def create_v1_blueprint(context: V1Context) -> Blueprint:
    """Create a fresh v1 blueprint with explicitly injected read callbacks."""
    blueprint = Blueprint("v1", __name__)

    @blueprint.get("/status")
    def v1_status():
        return _invoke(context.get_status)

    @blueprint.get("/sessions")
    def v1_sessions():
        return _invoke(context.list_sessions)

    @blueprint.get("/sessions/<path:session_name>")
    def v1_session(session_name: str):
        try:
            normalized = _validated_session_name(session_name)
        except InvalidInputError:
            return _error("invalid_input", "Entree invalide", 400)
        return _invoke(lambda: context.inspect_session(normalized))

    @blueprint.get("/playlist")
    def v1_playlist():
        try:
            limit = _validated_limit()
        except InvalidInputError:
            return _error("invalid_input", "Entree invalide", 400)
        return _invoke(lambda: context.get_playlist(limit or MAX_PLAYLIST_LIMIT))

    return blueprint


__all__ = ["V1Context", "create_v1_blueprint"]
