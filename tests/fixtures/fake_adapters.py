"""Deterministic fakes used to verify the adapter protocols locally."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeServoAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def set_named_angle(
        self, name: str, deg: float, log_enabled: bool = True
    ) -> None:
        self.calls.append(("set_named_angle", name, deg, log_enabled))

    def neutral(self) -> None:
        self.calls.append(("neutral",))

    def cleanup(self) -> None:
        self.calls.append(("cleanup",))

    def set_pitch_offset(self, servo_name: str, offset: float) -> None:
        self.calls.append(("set_pitch_offset", servo_name, offset))


class FakeAudioAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.callback = None

    def load(self, session_dir: str | Path) -> None:
        self.calls.append(("load", str(session_dir)))

    def play(self) -> None:
        self.calls.append(("play",))

    def pause(self) -> None:
        self.calls.append(("pause",))

    def resume(self) -> None:
        self.calls.append(("resume",))

    def stop(self, reason: str = "stop") -> None:
        self.calls.append(("stop", reason))

    def status(self) -> dict[str, Any]:
        self.calls.append(("status",))
        return {"running": False, "simulated": True}

    def set_on_track_finished(self, callback) -> None:
        self.callback = callback
        self.calls.append(("set_on_track_finished", callback))


class FakeBluetoothAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def scan(self) -> list[dict[str, str]]:
        self.calls.append(("scan",))
        return [{"mac": "00:11:22:33:44:55", "name": "Test speaker"}]

    def pair(self, address: str) -> dict[str, Any]:
        self.calls.append(("pair", address))
        return {"paired": True, "trusted": True, "connected": True}

    def connect(self, address: str) -> bool:
        self.calls.append(("connect", address))
        return True

    def info(self, address: str) -> dict[str, Any] | None:
        self.calls.append(("info", address))
        return {"address": address, "connected": True}


class FakeEsp32Adapter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def request(
        self, path: str, method: str = "GET", json_payload=None
    ) -> dict[str, Any]:
        self.calls.append(("request", path, method, json_payload))
        return {"ok": True, "path": path}


class FakeSmokeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def trigger(self, session_name: str) -> None:
        self.calls.append(("trigger", session_name))


class FakeGazeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.command: dict[str, Any] | None = {
            "mode": "track",
            "ts": 0.0,
            "neck": {"yaw_deg": 0.0},
        }

    def get_command(self) -> dict[str, Any] | None:
        self.calls.append(("get_command",))
        return self.command

    def stop(self, timeout: float = 1.0) -> None:
        self.calls.append(("stop", timeout))
