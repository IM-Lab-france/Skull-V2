"""Pure Bluetooth state model and BlueZ information parsing."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Iterable, Mapping


A2DP_AUDIO_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"
BLUETOOTH_ADDRESS_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_UUID_RE = re.compile(
    r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"
)
_PROPERTY_RE = re.compile(r"^\s*(Name|Alias|Paired|Trusted|Connected):\s*(.*?)\s*$")


def validate_bluetooth_address(address: str) -> str:
    """Return a normalized MAC or reject it before any external command."""
    value = str(address or "").strip()
    if not BLUETOOTH_ADDRESS_RE.fullmatch(value):
        raise ValueError("Adresse Bluetooth invalide")
    return value.upper()


def parse_bluez_properties(text: str) -> dict[str, Any]:
    """Parse only named BlueZ properties; UUIDs are handled separately."""
    properties: dict[str, Any] = {}
    for line in str(text or "").splitlines():
        match = _PROPERTY_RE.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        if key in {"Paired", "Trusted", "Connected"}:
            lowered = raw_value.lower()
            if lowered in {"yes", "no"}:
                properties[key.lower()] = lowered == "yes"
        elif key == "Name" or "name" not in properties:
            if raw_value:
                properties["name"] = raw_value
    return properties


def parse_bluez_uuids(text: str) -> frozenset[str]:
    """Return normalized UUIDs only; human-readable profile names are ignored."""
    return frozenset(match.group(0).lower() for match in _UUID_RE.finditer(str(text or "")))


def has_audio_sink_profile(uuids: Iterable[str]) -> bool:
    """Recognize A2DP Audio Sink only from its assigned UUID."""
    normalized = {str(value).strip().lower() for value in uuids}
    return A2DP_AUDIO_SINK_UUID in normalized


@dataclass(frozen=True, slots=True)
class BluetoothDeviceState:
    """One observation; ``None`` means that a property is not currently known."""

    address: str
    name: str | None
    discovered: bool | None
    paired: bool | None
    trusted: bool | None
    connected: bool | None
    audio_sink_capable: bool | None
    pulse_sink: str | None
    last_error: str | None
    updated_at: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", validate_bluetooth_address(self.address))

    @classmethod
    def from_bluez_info(
        cls,
        address: str,
        text: str,
        *,
        discovered: bool | None = True,
        pulse_sink: str | None = None,
        last_error: str | None = None,
        updated_at: float | None = None,
    ) -> "BluetoothDeviceState":
        properties = parse_bluez_properties(text)
        uuids = parse_bluez_uuids(text)
        return cls(
            address=address,
            name=properties.get("name"),
            discovered=discovered,
            paired=properties.get("paired"),
            trusted=properties.get("trusted"),
            connected=properties.get("connected"),
            audio_sink_capable=has_audio_sink_profile(uuids),
            pulse_sink=pulse_sink,
            last_error=last_error,
            updated_at=time.time() if updated_at is None else float(updated_at),
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "name": self.name,
            "discovered": self.discovered,
            "paired": self.paired,
            "trusted": self.trusted,
            "connected": self.connected,
            "audio_sink_capable": self.audio_sink_capable,
            "pulse_sink": self.pulse_sink,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }


__all__ = [
    "A2DP_AUDIO_SINK_UUID",
    "BLUETOOTH_ADDRESS_RE",
    "BluetoothDeviceState",
    "has_audio_sink_profile",
    "parse_bluez_properties",
    "parse_bluez_uuids",
    "validate_bluetooth_address",
]
