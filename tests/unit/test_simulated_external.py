"""State and failure tests for the SKULL-04.4 external simulators."""

from __future__ import annotations

import pytest

from adapters import BluetoothAdapter, ESP32Adapter, SmokeAdapter
import simulated_external
from simulated_external import (
    SimulatedBluetoothAdapter,
    SimulatedESP32Adapter,
    SimulatedESP32HTTPError,
    SimulatedSmokeAdapter,
    SimulatedSmokeHTTPError,
)
from simulation_clock import SimulatedClock


def test_bluetooth_states_are_distinct_and_calls_are_inspectable() -> None:
    clock = SimulatedClock()
    bluetooth = SimulatedBluetoothAdapter(clock=clock)
    bluetooth.add_device(
        "TEST-BT-01",
        "Synthetic headset",
        a2dp_profile=True,
        sink_present=True,
    )
    assert isinstance(bluetooth, BluetoothAdapter)

    assert bluetooth.info("TEST-BT-01")["discovered"] is False
    assert bluetooth.scan() == [{"mac": "TEST-BT-01", "name": "Synthetic headset"}]
    before_pair = bluetooth.info("TEST-BT-01")
    assert before_pair["discovered"] is True
    assert before_pair["paired"] is False
    assert before_pair["trusted"] is False
    assert before_pair["connected"] is False
    assert before_pair["sink_available"] is False

    final = bluetooth.pair("TEST-BT-01")
    assert final == {
        "address": "TEST-BT-01",
        "name": "Synthetic headset",
        "discovered": True,
        "paired": True,
        "trusted": True,
        "connected": True,
        "a2dp_profile": True,
        "sink_available": True,
    }
    assert [call["operation"] for call in bluetooth.calls] == [
        "info",
        "scan",
        "info",
        "pair",
        "trust",
        "connect",
    ]
    assert [entry["operation"] for entry in bluetooth.transitions] == [
        "scan",
        "pair",
        "trust",
        "connect",
    ]


def test_bluetooth_failure_leaves_intermediate_state_and_delays_are_logical() -> None:
    clock = SimulatedClock()
    bluetooth = SimulatedBluetoothAdapter(
        clock=clock,
        delays_s={"scan": 1.5},
        failures={"trust": TimeoutError("synthetic trust timeout")},
    )
    bluetooth.add_device("TEST-BT-02", "Synthetic speaker")
    bluetooth.scan()
    assert clock.monotonic() == 1.5

    with pytest.raises(TimeoutError, match="trust timeout"):
        bluetooth.pair("TEST-BT-02")
    state = bluetooth.info("TEST-BT-02")
    assert state["paired"] is True
    assert state["trusted"] is False
    assert state["connected"] is False


def test_bluetooth_can_be_connected_without_an_audio_sink() -> None:
    bluetooth = SimulatedBluetoothAdapter()
    bluetooth.add_device("TEST-BT-03", "Synthetic BLE device", a2dp_profile=False)
    bluetooth.scan()
    state = bluetooth.pair("TEST-BT-03")
    assert state["connected"] is True
    assert state["a2dp_profile"] is False
    assert state["sink_available"] is False


def test_esp32_status_controls_button_config_and_restart_are_recorded() -> None:
    esp32 = SimulatedESP32Adapter(button_count=3)
    assert isinstance(esp32, ESP32Adapter)
    assert esp32.request("/api/status")["relay"] is False
    assert esp32.request("/api/relay", "POST", {"on": True})["relay"] is True
    assert esp32.request("/api/auto-relay", "POST", {"enabled": True})[
        "auto_relay"
    ] is True
    esp32.request(
        "/api/button-config",
        "POST",
        {"button": 1, "category": "Accueil"},
    )
    assert esp32.request("/api/button-config")["states"] == ["", "Accueil", ""]
    assert esp32.request("/api/restart", "POST", {})["restart_count"] == 1
    assert esp32.calls == [
        {"path": "/api/status", "method": "GET", "json_payload": {}},
        {"path": "/api/relay", "method": "POST", "json_payload": {"on": True}},
        {
            "path": "/api/auto-relay",
            "method": "POST",
            "json_payload": {"enabled": True},
        },
        {
            "path": "/api/button-config",
            "method": "POST",
            "json_payload": {"button": 1, "category": "Accueil"},
        },
        {"path": "/api/button-config", "method": "GET", "json_payload": {}},
        {"path": "/api/restart", "method": "POST", "json_payload": {}},
    ]


def test_esp32_failures_and_delays_are_injectable_without_network() -> None:
    clock = SimulatedClock()
    esp32 = SimulatedESP32Adapter(
        clock=clock,
        delays_s={"/api/status": 2.0},
        failures={"/api/status": SimulatedESP32HTTPError(500)},
    )
    with pytest.raises(SimulatedESP32HTTPError) as error:
        esp32.request("/api/status")
    assert error.value.status_code == 500
    assert clock.monotonic() == 2.0
    assert esp32.calls == [
        {"path": "/api/status", "method": "GET", "json_payload": {}}
    ]


def test_smoke_records_success_timeout_and_http_error() -> None:
    clock = SimulatedClock()
    smoke = SimulatedSmokeAdapter(
        clock=clock,
        outcomes=("success", "timeout", "http_error"),
        http_status=503,
        delay_s=0.25,
    )
    assert isinstance(smoke, SmokeAdapter)

    smoke.trigger("Accueil")
    assert smoke.last_result == {
        "session_name": "Accueil",
        "outcome": "success",
        "status": "triggered",
    }

    with pytest.raises(TimeoutError):
        smoke.trigger("Accueil")
    assert smoke.last_result["status"] == "timeout"

    with pytest.raises(SimulatedSmokeHTTPError) as error:
        smoke.trigger("Accueil")
    assert error.value.status_code == 503
    assert smoke.last_result["http_status"] == 503
    assert [call["outcome"] for call in smoke.calls] == [
        "success",
        "timeout",
        "http_error",
    ]
    assert clock.monotonic() == pytest.approx(0.75)


def test_simulated_external_modules_do_not_load_platform_clients() -> None:
    forbidden_names = {"bluetooth", "dbus", "requests", "socket", "subprocess"}
    assert not forbidden_names.intersection(simulated_external.__dict__)
