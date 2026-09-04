from __future__ import annotations

import sys
import types
from pathlib import Path
from subprocess import CompletedProcess
from urllib.error import URLError

import pytest

from adapters import (
    AudioAdapter,
    BluetoothAdapter,
    ESP32Adapter,
    GazeAdapter,
    ServoAdapter,
    SmokeAdapter,
)
from adapters_runtime import (
    BluetoothctlAdapter,
    ESP32HTTPAdapter,
    GazeReceiverAdapter,
    PCA9685ServoAdapter,
    SyncPlayerAudioAdapter,
    WebhookSmokeAdapter,
)
from domain.errors import DependencyUnavailableError, InvalidInputError
from tests.fixtures.fake_adapters import (
    FakeAudioAdapter,
    FakeGazeAdapter,
    FakeServoAdapter,
)


def test_concrete_adapters_are_structurally_compatible() -> None:
    assert isinstance(PCA9685ServoAdapter(FakeServoAdapter()), ServoAdapter)
    assert isinstance(SyncPlayerAudioAdapter(FakeAudioAdapter()), AudioAdapter)
    assert isinstance(GazeReceiverAdapter(FakeGazeAdapter()), GazeAdapter)
    assert isinstance(
        BluetoothctlAdapter(runner=lambda *args, **kwargs: CompletedProcess([], 0)),
        BluetoothAdapter,
    )
    assert isinstance(
        ESP32HTTPAdapter("http://esp32.test", opener=lambda *args, **kwargs: None),
        ESP32Adapter,
    )
    assert isinstance(WebhookSmokeAdapter(), SmokeAdapter)


def test_servo_and_audio_adapters_delegate_without_constructing_platform_clients() -> None:
    servo = FakeServoAdapter()
    adapter = PCA9685ServoAdapter(servo)
    adapter.set_named_angle("jaw", 130.0, log_enabled=False)
    adapter.set_pitch_offset("jaw", 1.0)
    adapter.neutral()
    adapter.cleanup()
    assert servo.calls == [
        ("set_named_angle", "jaw", 130.0, False),
        ("set_pitch_offset", "jaw", 1.0),
        ("neutral",),
        ("cleanup",),
    ]

    audio = FakeAudioAdapter()
    audio_adapter = SyncPlayerAudioAdapter(audio)
    audio_adapter.load(Path("synthetic"))
    audio_adapter.play()
    audio_adapter.pause()
    audio_adapter.resume()
    audio_adapter.stop("test")
    assert audio.calls[:5] == [
        ("load", "synthetic"),
        ("play",),
        ("pause",),
        ("resume",),
        ("stop", "test"),
    ]


def test_boundary_failures_are_translated_without_exposing_original_detail() -> None:
    class BrokenServo(FakeServoAdapter):
        def set_named_angle(self, *args, **kwargs) -> None:
            raise OSError("private bus detail")

    with pytest.raises(DependencyUnavailableError, match="servo indisponible") as error:
        PCA9685ServoAdapter(BrokenServo()).set_named_angle("jaw", 90)
    assert "private" not in str(error.value)

    class BrokenAudio(FakeAudioAdapter):
        def play(self) -> None:
            raise RuntimeError("private audio detail")

    with pytest.raises(DependencyUnavailableError, match="lecture audio indisponible"):
        SyncPlayerAudioAdapter(BrokenAudio()).play()


def test_bluetooth_adapter_owns_command_parsing_and_pairing_workflow() -> None:
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        script = kwargs["input"]
        calls.append({"command": command, "script": script})
        if "devices" in script:
            output = "Device AA:BB:CC:DD:EE:FF Test speaker\n"
        elif "info" in script:
            output = "Connected: yes\nPaired: yes\nTrusted: yes\n"
        else:
            output = ""
        return CompletedProcess(command, 0, stdout=output, stderr="")

    adapter = BluetoothctlAdapter(
        runner=runner,
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
        scan_duration=0.0,
    )
    assert adapter.scan() == [{"mac": "AA:BB:CC:DD:EE:FF", "name": "Test speaker"}]
    assert adapter.pair("AA:BB:CC:DD:EE:FF")["connected"] is True
    assert adapter.connect("AA:BB:CC:DD:EE:FF") is True
    assert any("pair AA:BB:CC:DD:EE:FF" in call["script"] for call in calls)
    assert any("trust AA:BB:CC:DD:EE:FF" in call["script"] for call in calls)
    assert any("connect AA:BB:CC:DD:EE:FF" in call["script"] for call in calls)


def test_bluetooth_input_and_transport_failures_are_stable() -> None:
    adapter = BluetoothctlAdapter(
        runner=lambda *args, **kwargs: (_ for _ in ()).throw(
            FileNotFoundError("private executable path")
        )
    )
    with pytest.raises(InvalidInputError):
        adapter.info("not a mac")
    with pytest.raises(DependencyUnavailableError, match="bluetoothctl indisponible"):
        adapter.info("AA:BB:CC:DD:EE:FF")


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.payload


def test_esp32_adapter_validates_path_parses_json_and_maps_network_failures() -> None:
    requests: list[object] = []

    def opener(request, timeout):
        requests.append((request, timeout))
        return _Response(b'{"relay": true}')

    adapter = ESP32HTTPAdapter("http://esp32.test:80", opener=opener, timeout=0.2)
    assert adapter.request("/api/status") == {"relay": True}
    assert requests[0][1] == 0.2
    with pytest.raises(InvalidInputError):
        adapter.request("http://other.test/status")

    failing = ESP32HTTPAdapter(
        "http://esp32.test", opener=lambda *args, **kwargs: (_ for _ in ()).throw(
            URLError("private network detail")
        )
    )
    with pytest.raises(DependencyUnavailableError, match="Communication ESP32 indisponible"):
        failing.request("/api/status")

    invalid = ESP32HTTPAdapter(
        "http://esp32.test", opener=lambda *args, **kwargs: _Response(b"not-json")
    )
    with pytest.raises(DependencyUnavailableError, match="JSON ESP32 invalide"):
        invalid.request("/api/status")


def test_smoke_and_gaze_adapters_keep_effects_injectable() -> None:
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    smoke = WebhookSmokeAdapter("https://example.test/smoke", runner=runner)
    smoke.trigger("Demo")
    assert calls == []
    smoke.trigger("Accueil")
    assert calls == [["curl", "-sS", "-X", "POST", "https://example.test/smoke"]]

    refused = WebhookSmokeAdapter(
        "https://example.test/smoke",
        runner=lambda *args, **kwargs: CompletedProcess([], 22),
    )
    with pytest.raises(DependencyUnavailableError, match="Déclenchement fumée refuse"):
        refused.trigger("Accueil")

    gaze = GazeReceiverAdapter(FakeGazeAdapter())
    assert gaze.get_command()["mode"] == "track"
    gaze.stop(timeout=0.25)

    class BrokenGaze(FakeGazeAdapter):
        def get_command(self):
            raise OSError("private socket detail")

    with pytest.raises(DependencyUnavailableError, match="Réception gaze indisponible"):
        GazeReceiverAdapter(BrokenGaze()).get_command()


def test_runtime_adapter_module_does_not_import_raspberry_clients() -> None:
    forbidden = {"board", "busio", "adafruit_pca9685", "RPi"}
    assert not any(
        name in sys.modules
        or any(name.startswith(f"{prefix}.") for prefix in forbidden)
        for name in forbidden
    )
