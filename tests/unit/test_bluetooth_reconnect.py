from __future__ import annotations

import threading
import time

from services.bluetooth_reconnect import (
    BluetoothReconnectController,
    BluetoothReconnectWorker,
    ReconnectResult,
)


ADDRESS = "AA:BB:CC:DD:EE:FF"


def test_untrusted_device_is_degraded_without_connect_or_scan() -> None:
    calls: list[str] = []
    controller = BluetoothReconnectController(
        read_state=lambda address: {"trusted": False, "connected": False},
        connect_once=lambda address, timeout: calls.append("connect") or True,
    )

    result = controller.ensure(ADDRESS)

    assert result.reason == "not_trusted"
    assert result.connected is False
    assert result.attempts == 0
    assert calls == []


def test_already_connected_device_is_idempotent() -> None:
    calls: list[str] = []
    controller = BluetoothReconnectController(
        read_state=lambda address: {"trusted": True, "connected": True},
        connect_once=lambda address, timeout: calls.append("connect") or True,
    )

    result = controller.ensure(ADDRESS)

    assert result.reason == "already_connected"
    assert result.attempts == 0
    assert calls == []


def test_reconnect_uses_bounded_backoff_and_stops_after_success() -> None:
    state = {"trusted": True, "connected": False}
    calls: list[tuple[str, float]] = []
    waits: list[float] = []
    logs: list[str] = []

    def connect(address: str, timeout: float) -> bool:
        calls.append((address, timeout))
        if len(calls) == 2:
            state["connected"] = True
        return True

    controller = BluetoothReconnectController(
        read_state=lambda address: dict(state),
        connect_once=connect,
        max_attempts=3,
        connect_timeout=2.0,
        initial_delay=0.5,
        max_delay=2.0,
        wait=lambda delay: waits.append(delay) or False,
        log_attempt=logs.append,
    )

    result = controller.ensure(ADDRESS)

    assert result.reason == "connected"
    assert result.attempts == 2
    assert [timeout for _, timeout in calls] == [2.0, 2.0]
    assert waits == [0.5]
    assert logs == ["attempt=1", "attempt=2"]


def test_reconnect_publishes_degraded_after_max_attempts() -> None:
    waits: list[float] = []
    calls: list[str] = []
    controller = BluetoothReconnectController(
        read_state=lambda address: {"trusted": True, "connected": False},
        connect_once=lambda address, timeout: calls.append("connect") or False,
        max_attempts=3,
        initial_delay=0.5,
        max_delay=2.0,
        wait=lambda delay: waits.append(delay) or False,
    )

    result = controller.ensure(ADDRESS)

    assert result.reason == "degraded"
    assert result.connected is False
    assert result.attempts == 3
    assert calls == ["connect", "connect", "connect"]
    assert waits == [0.5, 1.0]


def test_reconnect_wait_is_interruptible() -> None:
    waits: list[float] = []
    controller = BluetoothReconnectController(
        read_state=lambda address: {"trusted": True, "connected": False},
        connect_once=lambda address, timeout: False,
        max_attempts=3,
        wait=lambda delay: waits.append(delay) or True,
    )

    result = controller.ensure(ADDRESS)

    assert result.reason == "cancelled"
    assert result.attempts == 1
    assert waits == [0.5]


def test_per_call_attempt_limit_cannot_exceed_global_limit() -> None:
    calls: list[str] = []
    controller = BluetoothReconnectController(
        read_state=lambda address: {"trusted": True, "connected": False},
        connect_once=lambda address, timeout: calls.append("connect") or False,
        max_attempts=2,
        wait=lambda delay: False,
    )

    result = controller.ensure(ADDRESS, max_attempts=10)

    assert result.reason == "degraded"
    assert result.attempts == 2
    assert len(calls) == 2


def _result(*, connected: bool, attempts: int, reason: str) -> ReconnectResult:
    return ReconnectResult(
        address=ADDRESS,
        state={"trusted": True, "connected": connected},
        connected=connected,
        trusted=True,
        attempts=attempts,
        reason=reason,
    )


def test_worker_retries_outside_request_path_until_connected() -> None:
    calls: list[str] = []
    results: list[ReconnectResult] = []
    connected = threading.Event()

    def reconnect(address: str) -> ReconnectResult:
        calls.append(address)
        is_connected = len(calls) >= 2
        if is_connected:
            connected.set()
        return _result(
            connected=is_connected,
            attempts=len(calls),
            reason="connected" if is_connected else "degraded",
        )

    worker = BluetoothReconnectWorker(
        reconnect=reconnect,
        retry_interval=0.1,
        on_result=results.append,
    )
    worker.start(ADDRESS)
    worker.start(ADDRESS)

    assert connected.wait(timeout=2.0)
    worker.stop(timeout=1.0)

    assert calls[:2] == [ADDRESS, ADDRESS]
    assert results[-1].reason == "connected"
    assert worker.last_result is results[-1]
    assert worker.last_attempt_ts > 0
    assert worker.alive is False


def test_worker_stop_interrupts_retry_wait() -> None:
    first_attempt = threading.Event()

    def reconnect(_address: str) -> ReconnectResult:
        first_attempt.set()
        return _result(connected=False, attempts=1, reason="degraded")

    worker = BluetoothReconnectWorker(reconnect=reconnect, retry_interval=10.0)
    worker.start(ADDRESS)
    assert first_attempt.wait(timeout=2.0)

    started = time.monotonic()
    worker.stop(timeout=1.0)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert worker.alive is False


def test_worker_start_is_idempotent_while_attempt_is_running() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def reconnect(address: str) -> ReconnectResult:
        calls.append(address)
        entered.set()
        release.wait(timeout=1.0)
        return _result(connected=True, attempts=1, reason="connected")

    worker = BluetoothReconnectWorker(reconnect=reconnect, retry_interval=10.0)
    worker.start(ADDRESS)
    assert entered.wait(timeout=2.0)

    worker.start(ADDRESS)
    assert calls == [ADDRESS]

    release.set()
    worker.stop(timeout=1.0)
    assert worker.alive is False
