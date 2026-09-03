from __future__ import annotations

import threading

from services.esp32_supervisor import ESP32Supervisor


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_failures_back_off_then_open_circuit_and_recover_manually() -> None:
    clock = FakeClock()
    outcomes = [RuntimeError("offline"), RuntimeError("offline"), RuntimeError("offline"), {"ok": True}]

    def probe():
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    supervisor = ESP32Supervisor(
        probe=probe,
        enabled=lambda: True,
        initial_backoff=5,
        max_backoff=20,
        failure_threshold=3,
        circuit_cooldown=30,
        clock=clock,
    )

    first = supervisor._probe_once("automatic")
    assert first.state == "degraded"
    assert first.failures == 1
    assert first.next_probe_at == 5

    clock.value = 5
    second = supervisor._probe_once("automatic")
    assert second.state == "degraded"
    assert second.failures == 2
    assert second.next_probe_at == 15

    clock.value = 15
    third = supervisor._probe_once("automatic")
    assert third.state == "circuit_open"
    assert third.failures == 3
    assert third.next_probe_at == 45

    clock.value = 20
    recovered = supervisor.manual_probe()
    assert recovered.state == "online"
    assert recovered.reachable is True
    assert recovered.failures == 0


def test_manual_probe_does_not_overlap_automatic_probe() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def probe():
        nonlocal calls
        calls += 1
        entered.set()
        release.wait(timeout=1.0)
        return {"ok": True}

    supervisor = ESP32Supervisor(probe=probe, enabled=lambda: True)
    thread = threading.Thread(target=supervisor.manual_probe)
    thread.start()
    assert entered.wait(timeout=1.0)

    busy = supervisor.manual_probe()
    assert busy.state == "probing"
    assert busy.busy is True
    assert calls == 1

    release.set()
    thread.join(timeout=1.0)
    assert not thread.is_alive()
