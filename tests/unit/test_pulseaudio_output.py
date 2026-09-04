from __future__ import annotations

from collections import deque
from subprocess import CompletedProcess

import pytest

import adapters_runtime as runtime
from adapters_runtime import PulseAudioOutputAdapter
from domain.errors import DependencyUnavailableError


ADDRESS = "AA:BB:CC:DD:EE:FF"
CARD = "bluez_card.AA_BB_CC_DD_EE_FF"
SINK = "bluez_output.AA_BB_CC_DD_EE_FF.1"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _pactl_runner(outputs: dict[tuple[str, ...], str], calls: list[dict]):
    def runner(command, **kwargs):
        calls.append({"command": command, "kwargs": kwargs})
        args = tuple(command[1:])
        return CompletedProcess(command, 0, stdout=outputs.get(args, ""), stderr="")

    return runner


def _working_outputs() -> dict[tuple[str, ...], str]:
    return {
        ("list", "short", "cards"): f"0\t{CARD}\tmodule-bluez5-device.c\n",
        ("list", "cards"): f"Name: {CARD}\n\tActive Profile: a2dp_sink\n",
        ("list", "short", "sinks"): f"1\t{SINK}\tmodule-bluez5-device.c\tIDLE\n",
        ("list", "sinks"): f"Name: {SINK}\n\tState: IDLE\n",
        ("get-default-sink",): f"{SINK}\n",
    }


def test_selects_a2dp_and_verifies_exact_default_sink_without_volume_change() -> None:
    calls: list[dict] = []
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(_working_outputs(), calls),
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
        wait_timeout=0.1,
    )

    result = adapter.select_for_bluetooth(ADDRESS)

    assert result == {
        "address": ADDRESS,
        "card": CARD,
        "profile": "a2dp_sink",
        "pulse_sink": SINK,
        "pulse_default": True,
        "pulse_state": "IDLE",
        "fallback_used": False,
    }
    commands = [call["command"] for call in calls]
    assert ["pactl", "set-card-profile", CARD, "a2dp_sink"] in commands
    assert ["pactl", "set-default-sink", SINK] in commands
    assert not any(command[-1] in {"set-volume", "set-sink-volume", "set-sink-mute"} for command in commands)
    assert all(call["kwargs"]["shell"] is False for call in calls)
    assert adapter.selected_for(ADDRESS)["pulse_sink"] == SINK


def test_accepts_native_pulseaudio_bluez_sink_name() -> None:
    pulse_sink = "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"
    outputs = {
        key: value.replace(SINK, pulse_sink)
        for key, value in _working_outputs().items()
    }
    calls: list[dict] = []
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, calls),
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
        wait_timeout=0.1,
    )

    result = adapter.select_for_bluetooth(ADDRESS)

    assert result["pulse_sink"] == pulse_sink
    assert result["pulse_default"] is True


def test_parses_pactl_sink_state_before_sink_name() -> None:
    outputs = _working_outputs()
    outputs[("list", "sinks")] = f"Sink #1\n\tState: IDLE\n\tName: {SINK}\n"
    calls: list[dict] = []
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, calls),
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
        wait_timeout=0.1,
    )

    result = adapter.select_for_bluetooth(ADDRESS)

    assert result["pulse_state"] == "IDLE"


def test_waits_for_delayed_sink_with_injected_clock() -> None:
    clock = Clock()
    outputs = _working_outputs()
    sink_reads = deque(["", "", outputs[("list", "short", "sinks")]])
    calls: list[dict] = []

    def runner(command, **kwargs):
        calls.append({"command": command, "kwargs": kwargs})
        args = tuple(command[1:])
        if args == ("list", "short", "sinks"):
            return CompletedProcess(command, 0, stdout=sink_reads.popleft(), stderr="")
        return CompletedProcess(command, 0, stdout=outputs.get(args, ""), stderr="")

    adapter = PulseAudioOutputAdapter(
        runner=runner,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        poll_interval=0.2,
        wait_timeout=1.0,
    )

    result = adapter.select_for_bluetooth(ADDRESS)

    assert result["pulse_sink"] == SINK
    assert clock.sleeps == [0.2, 0.2]


def test_rejects_suspended_or_missing_target_sink() -> None:
    outputs = _working_outputs()
    outputs[("list", "sinks")] = f"Name: {SINK}\n\tState: SUSPENDED\n"
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, []),
        sleep=lambda _: None,
        monotonic=lambda: 1.0,
        wait_timeout=0.1,
    )

    with pytest.raises(DependencyUnavailableError, match="suspendu"):
        adapter.select_for_bluetooth(ADDRESS)


def test_rejects_when_a2dp_profile_is_not_active() -> None:
    outputs = _working_outputs()
    outputs[("list", "cards")] = f"Name: {CARD}\n\tActive Profile: off\n"
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, []),
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
        wait_timeout=0.1,
    )

    with pytest.raises(DependencyUnavailableError, match="Profil A2DP"):
        adapter.select_for_bluetooth(ADDRESS)


def test_rejects_when_the_selected_sink_is_not_the_default() -> None:
    outputs = _working_outputs()
    outputs[("get-default-sink",)] = "some_other_sink\n"
    adapter = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, []),
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
        wait_timeout=0.1,
    )

    with pytest.raises(DependencyUnavailableError, match="non sélectionné"):
        adapter.select_for_bluetooth(ADDRESS)


def test_local_fallback_is_disabled_by_default_and_explicit_when_enabled() -> None:
    fallback = "alsa_output.local.stereo"
    outputs = _working_outputs()
    outputs[("list", "short", "sinks")] = ""
    outputs[("list", "sinks")] = f"Name: {fallback}\n\tState: IDLE\n"
    calls: list[dict] = []
    clock = Clock()
    disabled = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, calls),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        wait_timeout=0.2,
        poll_interval=0.1,
        fallback_sink=fallback,
        fallback_enabled=False,
    )
    with pytest.raises(DependencyUnavailableError, match="non apparu"):
        disabled.select_for_bluetooth(ADDRESS)

    clock = Clock()
    calls.clear()
    outputs[("get-default-sink",)] = f"{fallback}\n"
    enabled = PulseAudioOutputAdapter(
        runner=_pactl_runner(outputs, calls),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        wait_timeout=0.2,
        poll_interval=0.1,
        fallback_sink=fallback,
        fallback_enabled=True,
    )
    result = enabled.select_for_bluetooth(ADDRESS)

    assert result["pulse_sink"] == fallback
    assert result["fallback_used"] is True
    assert ["pactl", "set-default-sink", fallback] in [call["command"] for call in calls]


def test_sink_name_rejects_newline_injection() -> None:
    with pytest.raises(ValueError):
        PulseAudioOutputAdapter(fallback_sink="safe\nset-sink-mute")


def test_system_service_uses_the_canonical_user_pulseaudio_socket(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.delenv("PULSE_SERVER", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(runtime.os, "getuid", lambda: 1000, raising=False)

    adapter = PulseAudioOutputAdapter()

    assert adapter.command_runner.environment == {
        "PULSE_SERVER": "unix:/run/user/1000/pulse/native"
    }
