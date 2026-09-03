"""In-memory Bluetooth, ESP32, and smoke adapters for local simulations.

No class in this module opens a socket, starts a subprocess, or imports a
platform service.  Delays advance an injected clock and failures are injected
as exceptions so callers can test their error paths deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from adapters import BluetoothDevice, BluetoothStatus, ESP32Adapter, SmokeAdapter
from simulation_clock import Clock, SimulatedClock


class SimulatedESP32HTTPError(ConnectionError):
    """HTTP-like failure carrying a synthetic status code."""

    def __init__(self, status_code: int, message: str = "simulated HTTP error") -> None:
        super().__init__(message)
        self.status_code = int(status_code)


class SimulatedSmokeHTTPError(ConnectionError):
    """HTTP-like smoke webhook failure carrying a synthetic status code."""

    def __init__(self, status_code: int, message: str = "simulated HTTP error") -> None:
        super().__init__(message)
        self.status_code = int(status_code)


class _FaultPlan:
    """Apply deterministic delays and one-shot exception injections."""

    def __init__(
        self,
        clock: Clock,
        delays_s: Mapping[str, float] | None,
        failures: Mapping[str, BaseException | list[BaseException]] | None,
    ) -> None:
        self.clock = clock
        self.delays_s = dict(delays_s or {})
        self.failures = dict(failures or {})

    def before(self, operation: str, fallback: str | None = None) -> None:
        delay = self.delays_s.get(operation)
        if delay is None and fallback is not None:
            delay = self.delays_s.get(fallback)
        if delay is not None:
            self.clock.sleep(float(delay))

        failure = self.failures.get(operation)
        if failure is None and fallback is not None:
            failure = self.failures.get(fallback)
        if isinstance(failure, list):
            failure = failure.pop(0) if failure else None
        if failure is not None:
            raise failure


@dataclass
class _BluetoothState:
    address: str
    name: str
    visible: bool = True
    discovered: bool = False
    paired: bool = False
    trusted: bool = False
    connected: bool = False
    a2dp_profile: bool = True
    sink_present: bool = True


class SimulatedBluetoothAdapter:
    """Stateful BlueZ-like adapter with explicit transport states."""

    def __init__(
        self,
        devices: Iterable[Mapping[str, Any]] = (),
        *,
        clock: Clock | None = None,
        delays_s: Mapping[str, float] | None = None,
        failures: Mapping[str, BaseException | list[BaseException]] | None = None,
    ) -> None:
        self.clock = clock or SimulatedClock()
        self._faults = _FaultPlan(self.clock, delays_s, failures)
        self._devices: dict[str, _BluetoothState] = {}
        self.calls: list[dict[str, Any]] = []
        self.transitions: list[dict[str, Any]] = []
        for device in devices:
            self.add_device(
                str(device["address"]),
                str(device.get("name", "")),
                visible=bool(device.get("visible", True)),
                a2dp_profile=bool(device.get("a2dp_profile", True)),
                sink_present=bool(device.get("sink_present", True)),
            )

    def add_device(
        self,
        address: str,
        name: str,
        *,
        visible: bool = True,
        a2dp_profile: bool = True,
        sink_present: bool = True,
    ) -> None:
        """Register a synthetic device without probing the local adapter."""
        if not address:
            raise ValueError("address is required")
        self._devices[address] = _BluetoothState(
            address=address,
            name=name,
            visible=visible,
            a2dp_profile=a2dp_profile,
            sink_present=sink_present,
        )

    def _record(self, operation: str, **fields: Any) -> None:
        self.calls.append({"operation": operation, **fields})

    def _record_transition(self, state: _BluetoothState, operation: str) -> None:
        snapshot = dict(self._snapshot(state))
        snapshot["operation"] = operation
        self.transitions.append(snapshot)

    def _require(self, address: str) -> _BluetoothState:
        try:
            return self._devices[address]
        except KeyError as exc:
            raise ConnectionError(f"unknown simulated Bluetooth device: {address}") from exc

    def _snapshot(self, state: _BluetoothState) -> BluetoothStatus:
        return {
            "address": state.address,
            "name": state.name,
            "discovered": state.discovered,
            "paired": state.paired,
            "trusted": state.trusted,
            "connected": state.connected,
            "a2dp_profile": state.a2dp_profile,
            "sink_available": (
                state.connected and state.a2dp_profile and state.sink_present
            ),
        }

    def scan(self) -> list[BluetoothDevice]:
        self._record("scan")
        self._faults.before("scan")
        found: list[BluetoothDevice] = []
        for state in self._devices.values():
            if state.visible:
                state.discovered = True
                found.append({"mac": state.address, "name": state.name})
                self._record_transition(state, "scan")
        return found

    def pair(self, address: str) -> BluetoothStatus:
        """Run pair → trust → connect while retaining every state transition."""
        self._record("pair", address=address)
        self._faults.before("pair")
        state = self._require(address)
        if not state.discovered:
            raise ConnectionError("device must be discovered before pairing")
        state.paired = True
        self._record_transition(state, "pair")
        self.trust(address)
        self.connect(address)
        return self._snapshot(state)

    def trust(self, address: str) -> bool:
        """Synthetic intermediate operation used by the pairing workflow."""
        self._record("trust", address=address)
        self._faults.before("trust")
        state = self._require(address)
        if not state.paired:
            raise ConnectionError("device must be paired before trusting")
        state.trusted = True
        self._record_transition(state, "trust")
        return True

    def connect(self, address: str) -> bool:
        self._record("connect", address=address)
        self._faults.before("connect")
        state = self._require(address)
        if not state.paired or not state.trusted:
            raise ConnectionError("device must be paired and trusted before connecting")
        state.connected = True
        self._record_transition(state, "connect")
        return True

    def info(self, address: str) -> BluetoothStatus | None:
        self._record("info", address=address)
        self._faults.before("info")
        state = self._devices.get(address)
        return None if state is None else self._snapshot(state)


class SimulatedESP32Adapter:
    """Endpoint-compatible ESP32 state machine with inspectable requests."""

    def __init__(
        self,
        *,
        button_count: int = 5,
        clock: Clock | None = None,
        delays_s: Mapping[str, float] | None = None,
        failures: Mapping[str, BaseException | list[BaseException]] | None = None,
    ) -> None:
        if button_count <= 0:
            raise ValueError("button_count must be positive")
        self.button_count = int(button_count)
        self.clock = clock or SimulatedClock()
        self._faults = _FaultPlan(self.clock, delays_s, failures)
        self.relay = False
        self.auto_relay = False
        self.button_assignments = ["" for _ in range(self.button_count)]
        self.restart_count = 0
        self.calls: list[dict[str, Any]] = []

    def _status(self) -> dict[str, Any]:
        return {
            "relay": self.relay,
            "auto_relay": self.auto_relay,
            "button_assignments": list(self.button_assignments),
            "restart_count": self.restart_count,
        }

    def request(
        self,
        path: str,
        method: str = "GET",
        json_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        payload = dict(json_payload or {})
        self.calls.append(
            {"path": path, "method": method, "json_payload": payload}
        )
        self._faults.before(path, fallback="request")

        if path == "/api/status" and method == "GET":
            return self._status()

        if path == "/api/relay" and method == "POST":
            if not isinstance(payload.get("on"), bool):
                raise ValueError("/api/relay requires boolean 'on'")
            self.relay = payload["on"]
            return {"ok": True, "relay": self.relay}

        if path == "/api/auto-relay" and method == "POST":
            if not isinstance(payload.get("enabled"), bool):
                raise ValueError("/api/auto-relay requires boolean 'enabled'")
            self.auto_relay = payload["enabled"]
            return {"ok": True, "auto_relay": self.auto_relay}

        if path == "/api/button-config" and method == "GET":
            return {
                "ok": True,
                "states": list(self.button_assignments),
                "button_count": self.button_count,
            }

        if path == "/api/button-config" and method == "POST":
            try:
                button = int(payload["button"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("button index is required") from exc
            if not 0 <= button < self.button_count:
                raise ValueError("button index out of range")
            category = payload.get("category", payload.get("session", ""))
            if not isinstance(category, str):
                raise ValueError("button category must be a string")
            self.button_assignments[button] = category.strip()
            return {"ok": True, "states": list(self.button_assignments)}

        if path == "/api/restart" and method == "POST":
            self.restart_count += 1
            return {"ok": True, "restarted": True, "restart_count": self.restart_count}

        raise ValueError(f"unsupported simulated ESP32 request: {method} {path}")


class SimulatedSmokeAdapter:
    """Smoke trigger fake with success, timeout, and HTTP-error outcomes."""

    _VALID_OUTCOMES = {"success", "timeout", "http_error"}

    def __init__(
        self,
        *,
        outcomes: Iterable[str] = ("success",),
        http_status: int = 500,
        clock: Clock | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.clock = clock or SimulatedClock()
        self.outcomes = list(outcomes)
        if not self.outcomes:
            self.outcomes = ["success"]
        if any(outcome not in self._VALID_OUTCOMES for outcome in self.outcomes):
            raise ValueError("outcomes must be success, timeout, or http_error")
        self.http_status = int(http_status)
        self.delay_s = float(delay_s)
        self.calls: list[dict[str, Any]] = []
        self.last_result: dict[str, Any] | None = None

    def trigger(self, session_name: str) -> None:
        """Record a trigger, then raise only for the configured failure outcome."""
        self.clock.sleep(self.delay_s)
        outcome = self.outcomes.pop(0) if self.outcomes else "success"
        event: dict[str, Any] = {
            "session_name": session_name,
            "outcome": outcome,
        }
        self.calls.append(event)

        if outcome == "timeout":
            self.last_result = {**event, "status": "timeout"}
            raise TimeoutError("simulated smoke timeout")
        if outcome == "http_error":
            self.last_result = {
                **event,
                "status": "http_error",
                "http_status": self.http_status,
            }
            raise SimulatedSmokeHTTPError(self.http_status)

        self.last_result = {**event, "status": "triggered"}


__all__ = [
    "SimulatedBluetoothAdapter",
    "SimulatedESP32Adapter",
    "SimulatedESP32HTTPError",
    "SimulatedSmokeAdapter",
    "SimulatedSmokeHTTPError",
]
