from __future__ import annotations

from flask import Flask
from pathlib import Path

from api.bluetooth import BluetoothUiContext, create_bluetooth_blueprint
from domain.errors import OperationNotAllowedError


ADDRESS = "AA:BB:CC:DD:EE:FF"


def _app(
    *,
    calls: list[str],
    state: dict | None = None,
    failure: BaseException | None = None,
) -> Flask:
    current = state or {
        "address": ADDRESS,
        "discovered": True,
        "paired": False,
        "trusted": False,
        "connected": False,
        "audio_sink_capable": False,
        "pulse_sink": None,
    }

    def operation(name: str):
        def callback(address: str):
            calls.append(name)
            if failure is not None and name == "pair":
                raise failure
            return {"address": address, name: True}

        return callback

    context = BluetoothUiContext(
        scan=lambda: [{"mac": ADDRESS, "name": "Synthetic speaker"}],
        pair=operation("pair"),
        trust=operation("trust"),
        connect=operation("connect"),
        select_output=operation("select-output"),
        test_audio=lambda address, duration, volume: (
            calls.append(f"test-audio:{duration}:{volume}")
            or {"address": address, "played": True}
        ),
        refresh_state=lambda address: dict(current),
    )
    app = Flask(__name__)
    app.register_blueprint(create_bluetooth_blueprint(context), url_prefix="/bluetooth")
    return app


def test_scan_is_discovery_only() -> None:
    calls: list[str] = []
    response = _app(calls=calls).test_client().post("/bluetooth/scan")

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "operation": "scan",
        "state": None,
        "devices": [{"mac": ADDRESS, "name": "Synthetic speaker"}],
    }
    assert calls == []


def test_pair_does_not_chain_trust_or_connect_and_refreshes_state() -> None:
    calls: list[str] = []
    response = _app(calls=calls).test_client().post(
        "/bluetooth/pair", json={"address": ADDRESS}
    )

    assert response.status_code == 200
    assert calls == ["pair"]
    assert response.get_json()["state"]["connected"] is False


def test_failed_operation_still_refreshes_and_hides_technical_detail() -> None:
    calls: list[str] = []
    response = _app(
        calls=calls,
        failure=RuntimeError("SECRET /srv/skull bluetoothctl output"),
    ).test_client().post("/bluetooth/pair", json={"address": ADDRESS})

    assert response.status_code == 502
    body = response.get_json()
    assert calls == ["pair"]
    assert body["error"] == {
        "code": "operation_failed",
        "message": "Opération Bluetooth impossible",
    }
    assert body["state"]["address"] == ADDRESS
    assert "SECRET" not in response.get_data(as_text=True)
    assert "/srv/skull" not in response.get_data(as_text=True)
    assert "bluetoothctl" not in response.get_data(as_text=True)


def test_invalid_address_is_rejected_before_callback() -> None:
    calls: list[str] = []
    response = _app(calls=calls).test_client().post(
        "/bluetooth/connect", json={"address": "not-a-mac"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_input"
    assert calls == []


def test_audio_test_requires_explicit_confirmation_and_bounds() -> None:
    calls: list[str] = []
    client = _app(calls=calls).test_client()

    no_confirmation = client.post(
        "/bluetooth/test-audio",
        json={"address": ADDRESS, "confirm": False},
    )
    too_long = client.post(
        "/bluetooth/test-audio",
        json={"address": ADDRESS, "confirm": True, "duration_ms": 3001, "volume": 5},
    )

    assert no_confirmation.status_code == 400
    assert too_long.status_code == 400
    assert calls == []


def test_audio_operation_is_separate_and_uses_bounded_parameters() -> None:
    calls: list[str] = []
    response = _app(calls=calls).test_client().post(
        "/bluetooth/test-audio",
        json={"address": ADDRESS, "confirm": True, "duration_ms": 500, "volume": 5},
    )

    assert response.status_code == 200
    assert calls == ["test-audio:500:5"]


def test_not_ready_operation_has_actionable_stable_error() -> None:
    calls: list[str] = []

    def not_ready(address: str):
        raise OperationNotAllowedError("PulseAudio details must not leak")

    # Build a dedicated app so the callback is the one under test.
    app = Flask(__name__)
    app.register_blueprint(
        create_bluetooth_blueprint(
            BluetoothUiContext(
                scan=lambda: [],
                pair=lambda address: {},
                trust=lambda address: {},
                connect=lambda address: {},
                select_output=not_ready,
                test_audio=lambda address, duration, volume: {},
                refresh_state=lambda address: {"address": address, "connected": True},
            )
        ),
        url_prefix="/bluetooth",
    )
    response = app.test_client().post(
        "/bluetooth/select-output", json={"address": ADDRESS}
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == {
        "code": "not_ready",
        "message": "Cette opération n'est pas encore disponible",
    }
    assert "PulseAudio" not in response.get_data(as_text=True)


def test_interface_exposes_independent_states_and_routes() -> None:
    root = Path(__file__).parents[2]
    template = (root / "templates" / "index.html").read_text(encoding="utf-8")
    script = (root / "static" / "app.js").read_text(encoding="utf-8")

    for element_id in (
        "btStatePaired",
        "btStateTrusted",
        "btStateConnected",
        "btStateAudio",
        "btStatePulse",
    ):
        assert f'id="{element_id}"' in template
    assert "`/bluetooth/${operation}`" in script
    for operation in ("pair", "trust", "connect", "select-output", "test-audio"):
        assert f'runBluetoothOperation("{operation}"' in script
    assert 'fetch("/pair"' not in script
