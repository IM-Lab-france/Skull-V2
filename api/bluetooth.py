"""Explicit Bluetooth operations exposed to the Skull web interface.

The legacy ``/pair`` route remains available for old clients.  This blueprint
is deliberately separate so the new interface can request one transition at a
time and receive a refreshed, redacted state after every attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from flask import Blueprint, jsonify, request

from domain.bluetooth import validate_bluetooth_address
from domain.errors import (
    DependencyUnavailableError,
    DomainError,
    InvalidInputError,
    OperationNotAllowedError,
)


@dataclass(frozen=True, slots=True)
class BluetoothUiContext:
    """Callbacks injected by the application composition root."""

    scan: Callable[[], Sequence[Mapping[str, Any]]]
    pair: Callable[[str], Mapping[str, Any]]
    trust: Callable[[str], Mapping[str, Any]]
    connect: Callable[[str], Mapping[str, Any]]
    select_output: Callable[[str], Mapping[str, Any]]
    test_audio: Callable[[str, int, int], Mapping[str, Any]]
    refresh_state: Callable[[str], Mapping[str, Any] | None]


_PRIVATE_KEYS = {
    "cmd",
    "command",
    "error_detail",
    "file",
    "filename",
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


def _public_value(value: Any) -> Any:
    """Return JSON-safe data without returning command diagnostics."""
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


def _success(operation: str, *, state: Mapping[str, Any] | None, **data: Any):
    payload = {"ok": True, "operation": operation, "state": _public_value(state)}
    payload.update({key: _public_value(value) for key, value in data.items()})
    return jsonify(payload), 200


def _error(
    operation: str,
    code: str,
    message: str,
    status_code: int,
    state: Mapping[str, Any] | None,
):
    return (
        jsonify(
            {
                "ok": False,
                "operation": operation,
                "error": {"code": code, "message": message},
                "state": _public_value(state),
            }
        ),
        status_code,
    )


def _body() -> dict[str, Any]:
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise InvalidInputError("Objet JSON requis")
    return value


def _address(body: Mapping[str, Any]) -> str:
    value = body.get("address", body.get("mac", ""))
    try:
        return validate_bluetooth_address(value)
    except (TypeError, ValueError) as exc:
        raise InvalidInputError("Adresse Bluetooth invalide") from exc


def _refresh(context: BluetoothUiContext, address: str) -> Mapping[str, Any] | None:
    try:
        return context.refresh_state(address)
    except Exception:
        return None


def _run_device_operation(
    context: BluetoothUiContext,
    operation: str,
    address: str,
    callback: Callable[[str], Mapping[str, Any]],
):
    state: Mapping[str, Any] | None = None
    try:
        result = callback(address)
    except InvalidInputError:
        state = _refresh(context, address)
        return _error(operation, "invalid_input", "Entrée Bluetooth invalide", 400, state)
    except OperationNotAllowedError:
        state = _refresh(context, address)
        return _error(
            operation,
            "not_ready",
            "Cette opération n'est pas encore disponible",
            409,
            state,
        )
    except TimeoutError:
        state = _refresh(context, address)
        return _error(operation, "timeout", "Opération Bluetooth expirée", 504, state)
    except DependencyUnavailableError:
        state = _refresh(context, address)
        return _error(
            operation, "dependency_unavailable", "Bluetooth indisponible", 503, state
        )
    except DomainError:
        state = _refresh(context, address)
        return _error(operation, "operation_failed", "Opération Bluetooth impossible", 422, state)
    except Exception:
        state = _refresh(context, address)
        return _error(operation, "operation_failed", "Opération Bluetooth impossible", 502, state)

    state = _refresh(context, address)
    return _success(operation, state=state, result=result)


def create_bluetooth_blueprint(context: BluetoothUiContext) -> Blueprint:
    """Create the explicit operation surface used by the new Bluetooth UI."""
    blueprint = Blueprint("bluetooth", __name__)

    @blueprint.post("/scan")
    def scan():
        try:
            devices = context.scan()
        except TimeoutError:
            return _error("scan", "timeout", "Scan Bluetooth expiré", 504, None)
        except DependencyUnavailableError:
            return _error("scan", "dependency_unavailable", "Bluetooth indisponible", 503, None)
        except Exception:
            return _error("scan", "operation_failed", "Scan Bluetooth impossible", 502, None)
        return _success("scan", state=None, devices=list(devices))

    def device_route(operation: str, callback: Callable[[str], Mapping[str, Any]]):
        try:
            address = _address(_body())
        except InvalidInputError:
            return _error(operation, "invalid_input", "Adresse Bluetooth invalide", 400, None)
        return _run_device_operation(context, operation, address, callback)

    @blueprint.post("/pair")
    def pair():
        return device_route("pair", context.pair)

    @blueprint.post("/trust")
    def trust():
        return device_route("trust", context.trust)

    @blueprint.post("/connect")
    def connect():
        return device_route("connect", context.connect)

    @blueprint.post("/select-output")
    def select_output():
        return device_route("select-output", context.select_output)

    @blueprint.post("/test-audio")
    def test_audio():
        try:
            body = _body()
            address = _address(body)
            if body.get("confirm") is not True:
                raise InvalidInputError("Confirmation explicite requise")
            duration_ms = body.get("duration_ms", 500)
            volume = body.get("volume", 5)
            if (
                isinstance(duration_ms, bool)
                or not isinstance(duration_ms, int)
                or duration_ms < 100
                or duration_ms > 3000
                or isinstance(volume, bool)
                or not isinstance(volume, int)
                or volume < 0
                or volume > 20
            ):
                raise InvalidInputError("Paramètres audio hors limites")
        except InvalidInputError:
            return _error("test-audio", "invalid_input", "Confirmation ou paramètres audio invalides", 400, None)
        return _run_device_operation(
            context,
            "test-audio",
            address,
            lambda value: context.test_audio(value, duration_ms, volume),
        )

    return blueprint


__all__ = ["BluetoothUiContext", "create_bluetooth_blueprint"]
