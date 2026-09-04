"""SKULL-07.6: deterministic Bluetooth/audio scenarios without hardware."""

from __future__ import annotations

from collections import deque
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from adapters_runtime import PulseAudioOutputAdapter
from domain.errors import DependencyUnavailableError
from services.bluetooth_reconnect import BluetoothReconnectController
from simulated_audio import SimulatedAudioPlayer
from simulated_external import SimulatedBluetoothAdapter
from simulation_clock import SimulatedClock


ADDRESS = "AA:BB:CC:DD:EE:FF"
CARD = "bluez_card.AA_BB_CC_DD_EE_FF"
SINK = "bluez_output.AA_BB_CC_DD_EE_FF.1"


def _working_pactl_outputs() -> dict[tuple[str, ...], str]:
    return {
        ("list", "short", "cards"): f"0\t{CARD}\tmodule-bluez5-device.c\n",
        ("list", "cards"): f"Name: {CARD}\n\tActive Profile: a2dp_sink\n",
        ("list", "short", "sinks"): f"1\t{SINK}\tmodule-bluez5-device.c\tIDLE\n",
        ("list", "sinks"): f"Name: {SINK}\n\tState: IDLE\n",
        ("get-default-sink",): f"{SINK}\n",
    }


def _pactl_runner(
    outputs: dict[tuple[str, ...], str],
    *,
    delayed_sinks: deque[str] | None = None,
):
    def runner(command, **kwargs):
        args = tuple(command[1:])
        if args == ("list", "short", "sinks") and delayed_sinks is not None:
            stdout = delayed_sinks.popleft()
        else:
            stdout = outputs.get(args, "")
        return CompletedProcess(command, 0, stdout=stdout, stderr="")

    return runner


def _state(
    *,
    name: str = "JBL Quantum 360",
    a2dp_profile: bool = True,
    sink_present: bool = True,
) -> SimulatedBluetoothAdapter:
    bluetooth = SimulatedBluetoothAdapter()
    bluetooth.add_device(
        ADDRESS,
        name,
        a2dp_profile=a2dp_profile,
        sink_present=sink_present,
    )
    return bluetooth


def _audio_ready(status: dict[str, object]) -> bool:
    """Mirror the safety gate: transport alone is not an audio sink."""
    return bool(
        status.get("connected")
        and status.get("a2dp_profile")
        and status.get("sink_available")
    )


def test_scan_empty_is_immediate_and_deterministic() -> None:
    clock = SimulatedClock()
    bluetooth = SimulatedBluetoothAdapter(clock=clock)

    assert bluetooth.scan() == []
    assert clock.monotonic() == 0.0
    assert clock.sleep_calls == []
    assert [call["operation"] for call in bluetooth.calls] == ["scan"]


def test_jbl_a2dp_reaches_every_required_audio_state() -> None:
    bluetooth = _state(a2dp_profile=True, sink_present=True)

    assert bluetooth.scan() == [
        {"mac": ADDRESS, "name": "JBL Quantum 360"}
    ]
    paired = bluetooth.pair(ADDRESS)
    observed = bluetooth.info(ADDRESS)

    assert paired["discovered"] is True
    assert observed == {
        "address": ADDRESS,
        "name": "JBL Quantum 360",
        "discovered": True,
        "paired": True,
        "trusted": True,
        "connected": True,
        "a2dp_profile": True,
        "sink_available": True,
    }
    assert _audio_ready(observed)
    assert [entry["operation"] for entry in bluetooth.transitions] == [
        "scan",
        "pair",
        "trust",
        "connect",
    ]


def test_ble_non_audio_device_can_connect_but_never_becomes_audio_ready() -> None:
    bluetooth = _state(
        name="Synthetic BLE non-audio", a2dp_profile=False, sink_present=True
    )
    bluetooth.scan()
    bluetooth.pair(ADDRESS)

    observed = bluetooth.info(ADDRESS)
    assert observed["paired"] is True
    assert observed["trusted"] is True
    assert observed["connected"] is True
    assert observed["a2dp_profile"] is False
    assert observed["sink_available"] is False
    assert not _audio_ready(observed)


def test_pairing_refused_stops_before_trust_and_connection() -> None:
    bluetooth = SimulatedBluetoothAdapter(
        failures={"pair": PermissionError("synthetic pairing refusal")}
    )
    bluetooth.add_device(ADDRESS, "Synthetic refused device")
    bluetooth.scan()

    with pytest.raises(PermissionError, match="pairing refusal"):
        bluetooth.pair(ADDRESS)

    observed = bluetooth.info(ADDRESS)
    assert observed["discovered"] is True
    assert observed["paired"] is False
    assert observed["trusted"] is False
    assert observed["connected"] is False
    assert [call["operation"] for call in bluetooth.calls] == [
        "scan",
        "pair",
        "info",
    ]


def test_connection_without_sink_is_not_reported_as_audio_ready() -> None:
    bluetooth = _state(a2dp_profile=True, sink_present=False)
    bluetooth.scan()
    bluetooth.pair(ADDRESS)

    observed = bluetooth.info(ADDRESS)
    assert observed["connected"] is True
    assert observed["a2dp_profile"] is True
    assert observed["sink_available"] is False
    assert not _audio_ready(observed)


def test_sink_appearing_late_is_found_without_real_wait() -> None:
    clock = SimulatedClock()
    outputs = _working_pactl_outputs()
    delayed_sinks = deque(["", "", outputs[("list", "short", "sinks")]])
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, delayed_sinks=delayed_sinks),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        poll_interval=0.2,
        wait_timeout=1.0,
    )

    result = adapter.select_for_bluetooth(ADDRESS)

    assert result["pulse_sink"] == SINK
    assert result["pulse_default"] is True
    assert clock.monotonic() == pytest.approx(0.4)
    assert clock.sleep_calls == [0.2, 0.2]


def test_disappearance_during_playback_stops_audio_safely() -> None:
    clock = SimulatedClock()
    bluetooth = _state()
    bluetooth.scan()
    bluetooth.pair(ADDRESS)
    audio = SimulatedAudioPlayer(duration_s=60.0, clock=clock)
    audio.load("sessions/jbl")
    audio.play()
    audio.advance(3.0)

    # This is deliberate simulator control, not a production/private API call.
    bluetooth._devices[ADDRESS].connected = False
    observed = bluetooth.info(ADDRESS)
    if not observed or not observed["connected"]:
        audio.stop("bluetooth_disappeared")

    assert observed["connected"] is False
    assert audio.status()["state"] == "stopped"
    assert audio.status()["position_s"] == 3.0
    assert audio.status()["stop_reason"] == "bluetooth_disappeared"


def test_pulseaudio_timeout_is_bounded_and_secret_free() -> None:
    clock = SimulatedClock()

    def timeout_runner(command, **kwargs):
        raise TimeoutExpired(command, timeout=0.1)

    adapter = PulseAudioOutputAdapter(
        runner=timeout_runner,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        wait_timeout=10.0,
    )

    with pytest.raises(DependencyUnavailableError, match="PulseAudio indisponible"):
        adapter.select_for_bluetooth(ADDRESS)

    assert clock.monotonic() == 0.0
    assert clock.sleep_calls == []


def test_reconnection_uses_existing_trust_without_scan_or_pair() -> None:
    bluetooth = _state()
    bluetooth.scan()
    bluetooth.pair(ADDRESS)
    bluetooth._devices[ADDRESS].connected = False
    calls_before = len(bluetooth.calls)

    controller = BluetoothReconnectController(
        read_state=bluetooth.info,
        connect_once=lambda address, timeout: bluetooth.connect(address),
        wait=lambda _delay: False,
    )
    result = controller.ensure(ADDRESS)

    assert result.reason == "connected"
    assert result.attempts == 1
    assert [call["operation"] for call in bluetooth.calls[calls_before:]] == [
        "info",
        "connect",
        "info",
    ]


def test_stop_during_reconnect_wait_is_immediate_and_cancellable() -> None:
    clock = SimulatedClock()
    waits: list[float] = []

    def wait(delay: float) -> bool:
        waits.append(delay)
        clock.sleep(delay)
        return True

    controller = BluetoothReconnectController(
        read_state=lambda _address: {"trusted": True, "connected": False},
        connect_once=lambda _address, _timeout: False,
        wait=wait,
        max_attempts=3,
    )
    result = controller.ensure(ADDRESS)

    assert result.reason == "cancelled"
    assert result.attempts == 1
    assert waits == [0.5]
    assert clock.monotonic() == 0.5
    assert clock.sleep_calls == [0.5]
