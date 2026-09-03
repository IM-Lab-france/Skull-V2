"""Conformity tests for the SKULL-04.1 adapter boundaries."""

from __future__ import annotations

import sys
from pathlib import Path

from adapters import (
    AudioAdapter,
    BluetoothAdapter,
    ESP32Adapter,
    GazeAdapter,
    ServoAdapter,
    SmokeAdapter,
)
from tests.fixtures.fake_adapters import (
    FakeAudioAdapter,
    FakeBluetoothAdapter,
    FakeEsp32Adapter,
    FakeGazeAdapter,
    FakeServoAdapter,
    FakeSmokeAdapter,
)


def test_protocols_import_without_raspberry_modules() -> None:
    """The protocol module is safe to import on a Windows workstation."""
    forbidden = {"board", "busio", "adafruit_pca9685"}
    assert not any(
        name in sys.modules
        or any(name.startswith(f"{prefix}.") for prefix in forbidden)
        for name in forbidden
    )


def test_fake_adapters_conform_to_all_six_protocols() -> None:
    fakes = (
        (FakeServoAdapter(), ServoAdapter),
        (FakeAudioAdapter(), AudioAdapter),
        (FakeBluetoothAdapter(), BluetoothAdapter),
        (FakeEsp32Adapter(), ESP32Adapter),
        (FakeSmokeAdapter(), SmokeAdapter),
        (FakeGazeAdapter(), GazeAdapter),
    )
    for fake, protocol in fakes:
        assert isinstance(fake, protocol)


def test_fake_adapters_record_the_minimal_contract_calls(tmp_path: Path) -> None:
    servo = FakeServoAdapter()
    servo.set_named_angle("jaw", 130.0, log_enabled=False)
    servo.set_pitch_offset("jaw", 1.5)
    servo.neutral()
    servo.cleanup()
    assert servo.calls == [
        ("set_named_angle", "jaw", 130.0, False),
        ("set_pitch_offset", "jaw", 1.5),
        ("neutral",),
        ("cleanup",),
    ]

    audio = FakeAudioAdapter()
    audio.load(tmp_path / "session")
    audio.play()
    audio.pause()
    audio.resume()
    audio.stop("test")
    assert audio.status()["simulated"] is True
    assert [call[0] for call in audio.calls] == [
        "load",
        "play",
        "pause",
        "resume",
        "stop",
        "status",
    ]

    bluetooth = FakeBluetoothAdapter()
    assert bluetooth.scan()[0]["name"] == "Test speaker"
    assert bluetooth.pair("00:11:22:33:44:55")["paired"] is True
    assert bluetooth.connect("00:11:22:33:44:55") is True
    assert bluetooth.info("00:11:22:33:44:55")["connected"] is True

    esp32 = FakeEsp32Adapter()
    assert esp32.request("/status")["ok"] is True
    esp32.request("/relay", method="POST", json_payload={"enabled": True})
    assert esp32.calls[-1] == (
        "request",
        "/relay",
        "POST",
        {"enabled": True},
    )

    smoke = FakeSmokeAdapter()
    smoke.trigger("Accueil")
    assert smoke.calls == [("trigger", "Accueil")]

    gaze = FakeGazeAdapter()
    assert gaze.get_command()["mode"] == "track"
    gaze.stop(timeout=0.25)
    assert gaze.calls[-1] == ("stop", 0.25)
