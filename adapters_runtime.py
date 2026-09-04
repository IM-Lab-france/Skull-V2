"""Concrete adapters for the legacy Skull boundaries.

This module contains no hardware or network access at import time.  Every
platform client is imported or invoked only from an explicit constructor or
method, so tests can inject fakes and a Windows workstation can import the
module safely.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import os
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from adapters import (
    AudioAdapter,
    BluetoothAdapter,
    BluetoothDevice,
    BluetoothStatus,
    ESP32Adapter,
    GazeAdapter,
    ServoAdapter,
    SmokeAdapter,
)
from domain.bluetooth import (
    has_audio_sink_profile,
    BluetoothDeviceState,
    parse_bluez_properties,
    parse_bluez_uuids,
    validate_bluetooth_address,
)
from domain.errors import (
    DependencyUnavailableError,
    InvalidInputError,
    NotFoundError,
)
from services.bluetooth_commands import BluetoothCommandRunner


def _dependency_error(operation: str, exc: BaseException) -> DependencyUnavailableError:
    """Create a stable, secret-free error for a technical boundary failure."""
    return DependencyUnavailableError(f"{operation} indisponible")


def _map_boundary_error(operation: str, exc: BaseException) -> None:
    if isinstance(exc, (NotFoundError, InvalidInputError, DependencyUnavailableError)):
        raise exc
    if isinstance(exc, FileNotFoundError):
        raise _dependency_error(operation, exc) from exc
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, RuntimeError)):
        raise _dependency_error(operation, exc) from exc
    if isinstance(exc, (KeyError, TypeError, ValueError)):
        raise InvalidInputError(f"Commande {operation} invalide") from exc
    raise _dependency_error(operation, exc) from exc


class PCA9685ServoAdapter:
    """Adapt the existing ``rpi_hardware.Hardware`` façade to ``ServoAdapter``."""

    def __init__(self, hardware: ServoAdapter) -> None:
        self._hardware = hardware

    @classmethod
    def from_legacy(cls, address: int = 0x40, frequency: int = 50) -> "PCA9685ServoAdapter":
        from rpi_hardware import Hardware

        return cls(Hardware(address=address, frequency=frequency))

    def set_named_angle(self, name: str, deg: float, log_enabled: bool = True) -> None:
        try:
            self._hardware.set_named_angle(name, deg, log_enabled=log_enabled)
        except Exception as exc:
            _map_boundary_error("servo", exc)

    def neutral(self) -> None:
        try:
            self._hardware.neutral()
        except Exception as exc:
            _map_boundary_error("neutralisation servo", exc)

    def cleanup(self) -> None:
        try:
            self._hardware.cleanup()
        except Exception as exc:
            _map_boundary_error("nettoyage servo", exc)

    def set_pitch_offset(self, servo_name: str, offset: float) -> None:
        try:
            self._hardware.set_pitch_offset(servo_name, offset)
        except Exception as exc:
            _map_boundary_error("offset servo", exc)


class SyncPlayerAudioAdapter:
    """Expose the audio surface of the legacy ``SyncPlayer`` by injection."""

    def __init__(self, player: AudioAdapter) -> None:
        self._player = player

    @classmethod
    def from_legacy(cls) -> "SyncPlayerAudioAdapter":
        from sync_player import SyncPlayer

        return cls(SyncPlayer())

    def load(self, session_dir: str | Path) -> None:
        try:
            self._player.load(session_dir)
        except Exception as exc:
            _map_boundary_error("session audio", exc)

    def play(self) -> None:
        try:
            self._player.play()
        except Exception as exc:
            _map_boundary_error("lecture audio", exc)

    def pause(self) -> None:
        try:
            self._player.pause()
        except Exception as exc:
            _map_boundary_error("pause audio", exc)

    def resume(self) -> None:
        try:
            self._player.resume()
        except Exception as exc:
            _map_boundary_error("reprise audio", exc)

    def stop(self, reason: str = "stop") -> None:
        try:
            self._player.stop(reason=reason)
        except Exception as exc:
            _map_boundary_error("arrêt audio", exc)

    def status(self) -> Mapping[str, Any]:
        try:
            return dict(self._player.status())
        except Exception as exc:
            _map_boundary_error("état audio", exc)
            raise AssertionError("unreachable")

    def set_on_track_finished(self, callback) -> None:
        try:
            self._player.set_on_track_finished(callback)
        except Exception as exc:
            _map_boundary_error("callback audio", exc)

    def cleanup(self) -> None:
        cleanup = getattr(self._player, "cleanup", None)
        if callable(cleanup):
            try:
                cleanup()
            except Exception as exc:
                _map_boundary_error("nettoyage audio", exc)


Runner = Callable[..., subprocess.CompletedProcess[str]]


class BluetoothctlAdapter:
    """BlueZ adapter that owns command construction and output parsing."""

    _DEVICE_RE = re.compile(r"^Device\s+([^\s]+)(?:\s+(.*))?$")

    def __init__(
        self,
        command: str | tuple[str, ...] = "bluetoothctl",
        *,
        runner: Runner | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        timeout: float = 5.0,
        scan_duration: float = 5.0,
        poll_interval: float = 0.5,
    ) -> None:
        self.command = tuple(shlex.split(command)) if isinstance(command, str) else tuple(command)
        if not self.command:
            raise InvalidInputError("Commande Bluetooth vide")
        self.sleep = sleep
        self.monotonic = monotonic
        self.timeout = max(0.1, float(timeout))
        self.scan_duration = max(0.0, float(scan_duration))
        self.poll_interval = max(0.0, float(poll_interval))
        try:
            self.command_runner = BluetoothCommandRunner(
                self.command, runner=runner, timeout=self.timeout
            )
        except ValueError as exc:
            raise InvalidInputError("Commande Bluetooth vide") from exc

    @staticmethod
    def _address(address: str) -> str:
        try:
            return validate_bluetooth_address(address)
        except ValueError as exc:
            raise InvalidInputError("Adresse Bluetooth invalide")

    @staticmethod
    def _output(value: object) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value or "")

    def _run(self, *lines: str) -> subprocess.CompletedProcess[str]:
        commands = [line for line in lines if line]
        try:
            result = self.command_runner.run(commands)
        except Exception as exc:
            _map_boundary_error("bluetoothctl", exc)
            raise AssertionError("unreachable")
        return result

    @staticmethod
    def _require_success(result: subprocess.CompletedProcess[str], operation: str) -> None:
        if int(result.returncode) != 0:
            raise DependencyUnavailableError(f"{operation} Bluetooth refuse")

    def scan(self) -> list[BluetoothDevice]:
        with self.command_runner.operation():
            for command in ("power on", "agent on", "default-agent", "scan on"):
                self._require_success(self._run(command), "Scan")
            self.sleep(self.scan_duration)
            self._require_success(self._run("scan off"), "Scan")
            result = self._run("devices")
            self._require_success(result, "Scan")
            devices: list[BluetoothDevice] = []
            for line in self._output(result.stdout).splitlines():
                match = self._DEVICE_RE.match(line.strip())
                if match:
                    try:
                        address = self._address(match.group(1))
                    except InvalidInputError:
                        continue
                    devices.append({"mac": address, "name": match.group(2) or ""})
            return devices

    def info(self, address: str) -> BluetoothStatus | None:
        value = self._address(address)
        result = self._run(f"info {value}")
        if int(result.returncode) != 0:
            return None
        text = self._output(result.stdout)
        properties = parse_bluez_properties(text)
        uuids = parse_bluez_uuids(text)
        return BluetoothDeviceState(
            address=value,
            name=properties.get("name"),
            discovered=True,
            paired=properties.get("paired"),
            trusted=properties.get("trusted"),
            connected=properties.get("connected"),
            audio_sink_capable=has_audio_sink_profile(uuids),
            pulse_sink=None,
            last_error=None,
            updated_at=time.time(),
        ).as_mapping()

    def _wait_flag(self, address: str, key: str, desired: bool, timeout: float) -> bool:
        deadline = self.monotonic() + max(0.0, float(timeout))
        while True:
            status = self.info(address)
            if status and status.get(key) is desired:
                return True
            if self.monotonic() >= deadline:
                return False
            self.sleep(self.poll_interval)

    def pair(self, address: str) -> BluetoothStatus:
        value = self._address(address)
        with self.command_runner.operation():
            for command in ("power on", "agent on", "default-agent"):
                self._require_success(self._run(command), "Appairage")
            self._require_success(self._run(f"pair {value}"), "Appairage")
            if not self._wait_flag(value, "paired", True, 15.0):
                raise DependencyUnavailableError("Appairage Bluetooth expire")
            self._require_success(self._run(f"trust {value}"), "Confiance Bluetooth")
            if not self._wait_flag(value, "trusted", True, 8.0):
                raise DependencyUnavailableError("Confiance Bluetooth expiree")
            self._require_success(self._run(f"connect {value}"), "Connexion Bluetooth")
            if not self._wait_flag(value, "connected", True, 12.0):
                raise DependencyUnavailableError("Connexion Bluetooth expiree")
            return dict(self.info(value) or {})

    def connect(self, address: str) -> bool:
        value = self._address(address)
        with self.command_runner.operation():
            result = self._run(f"connect {value}")
            if int(result.returncode) != 0:
                return False
            return self._wait_flag(value, "connected", True, 3.0)


class PulseAudioOutputAdapter:
    """Select and verify one exact Bluetooth PulseAudio sink."""

    @staticmethod
    def _session_environment() -> dict[str, str] | None:
        """Target the per-user PulseAudio socket from a system service.

        A systemd service running as ``skull`` does not necessarily inherit the
        interactive session's ``XDG_RUNTIME_DIR``.  PulseAudio still exposes
        its canonical user socket under ``/run/user/<uid>``; using it avoids a
        false "PulseAudio unavailable" result while preserving explicit
        ``PULSE_SERVER`` and session overrides.
        """
        if not sys.platform.startswith("linux"):
            return None
        if os.environ.get("PULSE_SERVER") or os.environ.get("XDG_RUNTIME_DIR"):
            return None
        try:
            uid = os.getuid()
        except AttributeError:  # pragma: no cover - non-POSIX fallback
            return None
        return {"PULSE_SERVER": f"unix:/run/user/{uid}/pulse/native"}

    def __init__(
        self,
        command: str | tuple[str, ...] = "pactl",
        *,
        runner: Runner | None = None,
        timeout: float = 5.0,
        wait_timeout: float = 5.0,
        poll_interval: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        fallback_sink: str | None = None,
        fallback_enabled: bool = False,
    ) -> None:
        self.command = (
            tuple(shlex.split(command)) if isinstance(command, str) else tuple(command)
        )
        if not self.command:
            raise InvalidInputError("Commande PulseAudio vide")
        self.command_runner = BluetoothCommandRunner(
            self.command,
            runner=runner,
            timeout=max(0.1, float(timeout)),
            environment=self._session_environment(),
        )
        self.wait_timeout = max(0.1, float(wait_timeout))
        self.poll_interval = max(0.0, float(poll_interval))
        self.sleep = sleep
        self.monotonic = monotonic
        self.fallback_sink = (
            self._validate_sink_name(fallback_sink) if fallback_sink else None
        )
        self.fallback_enabled = bool(fallback_enabled and self.fallback_sink)
        self._selected: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _validate_sink_name(value: str | None) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 256 or any(
            char in text for char in "\r\n\x00"
        ):
            raise InvalidInputError("Identifiant sink invalide")
        return text

    @staticmethod
    def _address_prefix(address: str) -> tuple[str, ...]:
        value = validate_bluetooth_address(address)
        normalized = value.replace(":", "_")
        return (
            "bluez_sink." + normalized + ".",
            "bluez_output." + normalized + ".",
        )

    @staticmethod
    def _card_name(address: str, lines: list[str]) -> str | None:
        value = validate_bluetooth_address(address)
        expected = "bluez_card." + value.replace(":", "_")
        for line in lines:
            fields = line.strip().split()
            if len(fields) >= 2 and (
                fields[1] == expected or fields[1].startswith(expected + ".")
            ):
                return fields[1]
        return None

    @staticmethod
    def _sink_rows(text: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for line in str(text or "").splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[0].isdigit():
                rows.append(
                    {
                        "index": fields[0],
                        "name": fields[1],
                        "state": fields[-1].upper(),
                    }
                )
        return rows

    @staticmethod
    def _active_profile(text: str, card_name: str) -> str | None:
        current_name: str | None = None
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("Name:"):
                current_name = stripped.split(":", 1)[1].strip()
            elif current_name == card_name and stripped.startswith("Active Profile:"):
                return stripped.split(":", 1)[1].strip()
        return None

    @staticmethod
    def _sink_state(text: str, sink_name: str) -> str | None:
        current_name: str | None = None
        current_state: str | None = None
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("Sink #"):
                if current_name == sink_name:
                    return current_state
                current_name = None
                current_state = None
            elif stripped.startswith("Name:"):
                current_name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("State:"):
                current_state = stripped.split(":", 1)[1].strip().upper()
        return current_state if current_name == sink_name else None

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return self.command_runner.run_args(arguments)
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            raise DependencyUnavailableError("PulseAudio indisponible") from exc
        except (OSError, RuntimeError) as exc:
            raise DependencyUnavailableError("PulseAudio indisponible") from exc

    @staticmethod
    def _require_success(
        result: subprocess.CompletedProcess[str], operation: str
    ) -> None:
        if int(result.returncode) != 0:
            raise DependencyUnavailableError(f"{operation} PulseAudio refuse")

    def _find_sink(self, address: str) -> str | None:
        result = self._run("list", "short", "sinks")
        self._require_success(result, "Lecture des sinks")
        prefixes = self._address_prefix(address)
        matches = [
            row["name"]
            for row in self._sink_rows(result.stdout)
            if any(row["name"].startswith(prefix) for prefix in prefixes)
        ]
        return matches[0] if len(matches) == 1 else None

    def _wait_sink(self, address: str) -> str | None:
        deadline = self.monotonic() + self.wait_timeout
        max_attempts = int(self.wait_timeout / max(self.poll_interval, 0.05)) + 2
        attempts = 0
        while True:
            sink = self._find_sink(address)
            if sink:
                return sink
            attempts += 1
            if attempts >= max_attempts or self.monotonic() >= deadline:
                return None
            self.sleep(self.poll_interval)

    def _verify_sink(self, sink_name: str) -> str:
        state_result = self._run("list", "sinks")
        self._require_success(state_result, "Vérification du sink")
        sink_state = self._sink_state(state_result.stdout, sink_name)
        if sink_state is None or sink_state == "SUSPENDED":
            raise DependencyUnavailableError("Sink PulseAudio suspendu ou absent")
        default_result = self._run("get-default-sink")
        self._require_success(default_result, "Vérification du sink par défaut")
        default_text = str(default_result.stdout or "").strip()
        default_name = default_text.splitlines()[0] if default_text else ""
        if default_name != sink_name:
            raise DependencyUnavailableError("Sink PulseAudio non sélectionné")
        return sink_state

    def select_for_bluetooth(self, address: str) -> dict[str, Any]:
        value = validate_bluetooth_address(address)
        with self.command_runner.operation():
            cards = self._run("list", "short", "cards")
            self._require_success(cards, "Lecture de la carte Bluetooth")
            card_name = self._card_name(value, str(cards.stdout or "").splitlines())
            if not card_name:
                raise DependencyUnavailableError("Carte Bluetooth audio absente")
            profile = self._run("set-card-profile", card_name, "a2dp_sink")
            self._require_success(profile, "Sélection du profil A2DP")
            profiles = self._run("list", "cards")
            self._require_success(profiles, "Vérification du profil A2DP")
            active = self._active_profile(profiles.stdout, card_name)
            if not active or not active.startswith("a2dp_sink"):
                raise DependencyUnavailableError("Profil A2DP non actif")

            sink_name = self._wait_sink(value)
            fallback_used = False
            if sink_name is None:
                if not self.fallback_enabled or not self.fallback_sink:
                    raise DependencyUnavailableError("Sink Bluetooth non apparu")
                sink_name = self.fallback_sink
                fallback_used = True
            selected = self._run("set-default-sink", sink_name)
            self._require_success(selected, "Sélection du sink")
            sink_state = self._verify_sink(sink_name)
            result = {
                "address": value,
                "card": card_name,
                "profile": active,
                "pulse_sink": sink_name,
                "pulse_default": True,
                "pulse_state": sink_state,
                "fallback_used": fallback_used,
            }
            self._selected[value] = dict(result)
            return result

    def selected_for(self, address: str) -> dict[str, Any] | None:
        value = validate_bluetooth_address(address)
        selected = self._selected.get(value)
        return None if selected is None else dict(selected)


class ESP32HTTPAdapter:
    """HTTP/JSON adapter with bounded transport and stable domain errors."""

    def __init__(
        self,
        base_url: str,
        *,
        opener: Callable[..., Any] = urlopen,
        timeout: float = 3.0,
    ) -> None:
        parsed = urlparse(str(base_url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidInputError("Adresse ESP32 invalide")
        self.base_url = str(base_url).rstrip("/")
        self.opener = opener
        self.timeout = max(0.1, float(timeout))

    def request(
        self,
        path: str,
        method: str = "GET",
        json_payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if not isinstance(path, str) or not path.startswith("/") or "://" in path:
            raise InvalidInputError("Chemin ESP32 invalide")
        method = str(method).upper()
        payload = None if json_payload is None else json.dumps(dict(json_payload)).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=payload, headers=headers, method=method)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise _dependency_error("Communication ESP32", exc) from exc
        except Exception as exc:
            raise _dependency_error("Communication ESP32", exc) from exc
        if not raw:
            return {}
        try:
            result = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DependencyUnavailableError("Reponse JSON ESP32 invalide") from exc
        if not isinstance(result, dict):
            raise DependencyUnavailableError("Reponse ESP32 invalide")
        return result


class WebhookSmokeAdapter:
    """Trigger the existing smoke webhook without exposing its URL."""

    def __init__(
        self,
        url: str = "",
        *,
        runner: Runner | None = None,
        timeout: float = 2.0,
    ) -> None:
        self.url = str(url or "").strip()
        self.runner = runner or subprocess.run
        self.timeout = max(0.1, float(timeout))

    def trigger(self, session_name: str) -> None:
        if not self.url or str(session_name).strip().casefold() != "accueil":
            return
        try:
            result = self.runner(
                ["curl", "-sS", "-X", "POST", self.url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except Exception as exc:
            _map_boundary_error("Déclenchement fumée", exc)
            return
        if int(result.returncode) != 0:
            raise DependencyUnavailableError("Déclenchement fumée refuse")


class GazeReceiverAdapter:
    """Adapt the UDP gaze receiver with explicit ownership and cleanup."""

    def __init__(self, receiver: GazeAdapter) -> None:
        self._receiver = receiver

    @classmethod
    def from_legacy(
        cls, host: str = "127.0.0.1", port: int = 5005
    ) -> "GazeReceiverAdapter":
        from gaze_receiver import GazeReceiver

        return cls(GazeReceiver(host=host, port=port))

    def get_command(self) -> Mapping[str, Any] | None:
        try:
            command = self._receiver.get_command()
        except Exception as exc:
            _map_boundary_error("Réception gaze", exc)
            raise AssertionError("unreachable")
        return None if command is None else dict(command)

    def stop(self, timeout: float = 1.0) -> None:
        try:
            self._receiver.stop(timeout=timeout)
        except Exception as exc:
            _map_boundary_error("Arrêt gaze", exc)


__all__ = [
    "BluetoothctlAdapter",
    "PulseAudioOutputAdapter",
    "ESP32HTTPAdapter",
    "GazeReceiverAdapter",
    "PCA9685ServoAdapter",
    "SyncPlayerAudioAdapter",
    "WebhookSmokeAdapter",
]
