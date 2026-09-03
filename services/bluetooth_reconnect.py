"""Bounded, cancellable Bluetooth reconnection policy."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any


@dataclass(frozen=True, slots=True)
class ReconnectResult:
    address: str
    state: Mapping[str, Any] | None
    connected: bool
    trusted: bool | None
    attempts: int
    reason: str

    def as_mapping(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "state": None if self.state is None else dict(self.state),
            "connected": self.connected,
            "trusted": self.trusted,
            "attempts": self.attempts,
            "reason": self.reason,
        }


class BluetoothReconnectController:
    """Reconnect only trusted devices, with bounded backoff and cancellation."""

    def __init__(
        self,
        *,
        read_state: Callable[[str], Mapping[str, Any] | None],
        connect_once: Callable[[str, float], bool],
        max_attempts: int = 3,
        connect_timeout: float = 3.0,
        initial_delay: float = 0.5,
        max_delay: float = 8.0,
        wait: Callable[[float], bool] | None = None,
        cancel_event: threading.Event | None = None,
        log_attempt: Callable[[str], None] | None = None,
    ) -> None:
        self.read_state = read_state
        self.connect_once = connect_once
        self.max_attempts = max(1, int(max_attempts))
        self.connect_timeout = max(0.1, float(connect_timeout))
        self.initial_delay = max(0.0, float(initial_delay))
        self.max_delay = max(self.initial_delay, float(max_delay))
        self.cancel_event = cancel_event or threading.Event()
        self.wait = wait or self.cancel_event.wait
        self.log_attempt = log_attempt or (lambda _message: None)
        self._last_result: ReconnectResult | None = None

    @property
    def last_result(self) -> ReconnectResult | None:
        return self._last_result

    def cancel(self) -> None:
        self.cancel_event.set()

    def ensure(
        self, address: str, *, max_attempts: int | None = None
    ) -> ReconnectResult:
        state = self._read(address)
        connected = self._flag(state, "connected")
        trusted = self._flag_or_none(state, "trusted")
        if connected is True:
            return self._finish(address, state, True, trusted, 0, "already_connected")
        if trusted is not True:
            reason = "not_trusted" if trusted is False else "state_unavailable"
            return self._finish(address, state, False, trusted, 0, reason)

        attempts_limit = max(
            1, min(self.max_attempts, int(max_attempts or self.max_attempts))
        )
        delay = self.initial_delay
        for attempt in range(1, attempts_limit + 1):
            if self.cancel_event.is_set():
                return self._finish(address, state, False, trusted, attempt - 1, "cancelled")
            self.log_attempt(f"attempt={attempt}")
            try:
                self.connect_once(address, self.connect_timeout)
            except Exception:
                # The next state read is authoritative; technical details stay out
                # of the policy result and logs.
                pass
            state = self._read(address)
            connected = self._flag(state, "connected")
            trusted = self._flag_or_none(state, "trusted")
            if connected is True:
                return self._finish(address, state, True, trusted, attempt, "connected")
            if attempt == attempts_limit:
                break
            if self.wait(delay):
                return self._finish(address, state, False, trusted, attempt, "cancelled")
            delay = min(self.max_delay, max(0.1, delay * 2 or 0.1))

        return self._finish(address, state, False, trusted, attempts_limit, "degraded")

    def _read(self, address: str) -> Mapping[str, Any] | None:
        try:
            value = self.read_state(address)
        except Exception:
            return None
        return dict(value) if isinstance(value, Mapping) else None

    @staticmethod
    def _flag(state: Mapping[str, Any] | None, key: str) -> bool | None:
        value = state.get(key) if state else None
        return value if isinstance(value, bool) else None

    @classmethod
    def _flag_or_none(cls, state: Mapping[str, Any] | None, key: str) -> bool | None:
        return cls._flag(state, key)

    def _finish(
        self,
        address: str,
        state: Mapping[str, Any] | None,
        connected: bool,
        trusted: bool | None,
        attempts: int,
        reason: str,
    ) -> ReconnectResult:
        result = ReconnectResult(address, state, connected, trusted, attempts, reason)
        self._last_result = result
        return result


class BluetoothReconnectWorker:
    """Run one bounded reconnect policy outside the HTTP request path."""

    def __init__(
        self,
        *,
        reconnect: Callable[[str], ReconnectResult],
        retry_interval: float = 10.0,
        on_result: Callable[[ReconnectResult], None] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.reconnect = reconnect
        self.retry_interval = max(0.1, float(retry_interval))
        self.on_result = on_result or (lambda _result: None)
        self.clock = clock
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._address: str | None = None
        self._thread: threading.Thread | None = None
        self._last_result: ReconnectResult | None = None
        self._last_attempt_ts = 0.0
        self._busy = False

    @property
    def last_result(self) -> ReconnectResult | None:
        with self._state_lock:
            return self._last_result

    @property
    def last_attempt_ts(self) -> float:
        with self._state_lock:
            return self._last_attempt_ts

    @property
    def alive(self) -> bool:
        with self._state_lock:
            return bool(self._thread and self._thread.is_alive())

    @property
    def busy(self) -> bool:
        """Whether a reconnect policy is currently talking to BlueZ."""
        with self._state_lock:
            return self._busy

    def start(self, address: str) -> None:
        value = str(address or "").strip()
        if not value:
            return
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return
            self._address = value
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="skull-bt-reconnect",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        with self._state_lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._state_lock:
                address = self._address
                self._last_attempt_ts = self.clock()
                self._busy = bool(address)
            if not address:
                return
            try:
                result = self.reconnect(address)
            except Exception:
                result = ReconnectResult(
                    address=address,
                    state=None,
                    connected=False,
                    trusted=None,
                    attempts=0,
                    reason="worker_error",
                )
            with self._state_lock:
                self._last_result = result
            try:
                self.on_result(result)
            except Exception:
                pass
            with self._state_lock:
                self._busy = False
            if self._stop_event.wait(self.retry_interval):
                return


__all__ = [
    "BluetoothReconnectController",
    "BluetoothReconnectWorker",
    "ReconnectResult",
]
