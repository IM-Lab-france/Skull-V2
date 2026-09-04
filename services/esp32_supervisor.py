"""Background supervision for the ESP32 endpoint.

The supervisor owns automatic status polling.  HTTP reads consume its last
snapshot and explicit manual checks use the same single-probe gate.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any


@dataclass(frozen=True, slots=True)
class ESP32ProbeSnapshot:
    state: str = "disabled"
    reachable: bool = False
    payload: Mapping[str, Any] | None = None
    failures: int = 0
    last_checked: float | None = None
    next_probe_at: float | None = None
    source: str = "none"
    error: str | None = None
    busy: bool = False

    def public(self) -> dict[str, Any]:
        """Return metadata safe for the web API; omit the remote payload."""
        return {
            "state": self.state,
            "reachable": self.reachable,
            "failures": self.failures,
            "last_checked": self.last_checked,
            "next_probe_at": self.next_probe_at,
            "source": self.source,
            "busy": self.busy,
        }


class ESP32Supervisor:
    """Poll one endpoint with bounded backoff and a small circuit breaker."""

    def __init__(
        self,
        *,
        probe: Callable[[], Mapping[str, Any]],
        enabled: Callable[[], bool],
        interval: float = 5.0,
        initial_backoff: float = 5.0,
        max_backoff: float = 60.0,
        failure_threshold: int = 3,
        circuit_cooldown: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.probe = probe
        self.enabled = enabled
        self.interval = max(0.1, float(interval))
        self.initial_backoff = max(0.1, float(initial_backoff))
        self.max_backoff = max(self.initial_backoff, float(max_backoff))
        self.failure_threshold = max(1, int(failure_threshold))
        self.circuit_cooldown = max(0.1, float(circuit_cooldown))
        self.clock = clock
        self._state_lock = threading.RLock()
        self._probe_lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = ESP32ProbeSnapshot()

    @property
    def alive(self) -> bool:
        with self._state_lock:
            return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._wake_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="skull-esp32-supervisor",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        with self._state_lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))

    def wake(self) -> None:
        """Wake the poller after a configuration change or manual request."""
        self._wake_event.set()

    def snapshot(self) -> ESP32ProbeSnapshot:
        with self._state_lock:
            snapshot = self._snapshot
        if self._probe_lock.locked():
            return replace(snapshot, state="probing", busy=True)
        return snapshot

    def manual_probe(self) -> ESP32ProbeSnapshot:
        """Run one explicit bounded probe, unless another probe is active."""
        if not self._is_enabled():
            self._publish_disabled()
            return self.snapshot()
        if not self._probe_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            return self._probe_once("manual", lock_acquired=True)
        finally:
            self._probe_lock.release()

    def _is_enabled(self) -> bool:
        try:
            return bool(self.enabled())
        except Exception:
            return False

    def _publish_disabled(self) -> None:
        with self._state_lock:
            self._snapshot = ESP32ProbeSnapshot(state="disabled", source="none")

    def _publish(self, snapshot: ESP32ProbeSnapshot) -> ESP32ProbeSnapshot:
        with self._state_lock:
            self._snapshot = snapshot
        return snapshot

    def _probe_once(
        self, source: str, *, lock_acquired: bool = False
    ) -> ESP32ProbeSnapshot:
        acquired_here = False
        if not lock_acquired:
            acquired_here = self._probe_lock.acquire(blocking=False)
            if not acquired_here:
                return self.snapshot()
        try:
            checked_at = self.clock()
            try:
                payload = self.probe()
                if not isinstance(payload, Mapping):
                    raise ValueError("invalid_payload")
            except Exception:
                previous = self.snapshot()
                failures = previous.failures + 1
                if failures >= self.failure_threshold:
                    state = "circuit_open"
                    delay = self.circuit_cooldown
                else:
                    state = "degraded"
                    delay = min(
                        self.max_backoff,
                        self.initial_backoff * (2 ** max(0, failures - 1)),
                    )
                return self._publish(
                    ESP32ProbeSnapshot(
                        state=state,
                        reachable=False,
                        failures=failures,
                        last_checked=checked_at,
                        next_probe_at=checked_at + delay,
                        source=source,
                        error="probe_failed",
                    )
                )

            return self._publish(
                ESP32ProbeSnapshot(
                    state="online",
                    reachable=True,
                    payload=dict(payload),
                    failures=0,
                    last_checked=checked_at,
                    next_probe_at=checked_at + self.interval,
                    source=source,
                )
            )
        finally:
            if acquired_here:
                self._probe_lock.release()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._is_enabled():
                self._publish_disabled()
                self._wake_event.wait(1.0)
                self._wake_event.clear()
                continue

            snapshot = self.snapshot()
            now = self.clock()
            due_at = snapshot.next_probe_at
            if due_at is not None and now < due_at:
                self._wake_event.wait(min(due_at - now, 1.0))
                self._wake_event.clear()
                continue

            self._probe_once("automatic")


__all__ = ["ESP32ProbeSnapshot", "ESP32Supervisor"]
