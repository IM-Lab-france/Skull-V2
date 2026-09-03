from __future__ import annotations

from subprocess import CompletedProcess
import threading
import time

import pytest

from services.bluetooth_commands import BluetoothCommandRunner


def test_runner_uses_argument_list_timeout_and_normalized_redacted_output() -> None:
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return CompletedProcess(
            command,
            0,
            stdout="\x1b[31msecret=synthetic-value\x1b[0m\r\n",
            stderr="https://user:password@synthetic.invalid\r\n",
        )

    executor = BluetoothCommandRunner(
        ("bluetoothctl", "--test"), runner=runner, timeout=1.25
    )
    result = executor.run(["info AA:BB:CC:DD:EE:FF"])

    assert calls[0]["command"] == ["bluetoothctl", "--test"]
    assert calls[0]["shell"] is False
    assert calls[0]["timeout"] == 1.25
    assert calls[0]["input"] == "info AA:BB:CC:DD:EE:FF\nquit\n"
    assert "synthetic-value" not in result.stdout
    assert "password@" not in result.stderr
    assert "\x1b" not in result.stdout
    assert result.stdout.endswith("\n")


def test_runner_rejects_embedded_newline_before_invoking_process() -> None:
    calls: list[object] = []
    executor = BluetoothCommandRunner(
        "bluetoothctl", runner=lambda *args, **kwargs: calls.append(args)
    )

    with pytest.raises(ValueError):
        executor.run(["pair AA:BB:CC:DD:EE:FF\nquit"])

    assert calls == []


def test_runner_serializes_concurrent_operations() -> None:
    active = 0
    maximum = 0
    state_lock = threading.Lock()
    entered = threading.Event()
    release = threading.Event()

    def runner(command, **kwargs):
        nonlocal active, maximum
        with state_lock:
            active += 1
            maximum = max(maximum, active)
        entered.set()
        release.wait(timeout=1.0)
        with state_lock:
            active -= 1
        return CompletedProcess(command, 0, stdout="", stderr="")

    first_executor = BluetoothCommandRunner("bluetoothctl", runner=runner)
    second_executor = BluetoothCommandRunner("bluetoothctl", runner=runner)
    first = threading.Thread(target=lambda: first_executor.run(["scan on"]))
    second = threading.Thread(target=lambda: second_executor.run(["scan on"]))
    first.start()
    assert entered.wait(timeout=1.0)
    second.start()
    time.sleep(0.05)

    with state_lock:
        assert maximum == 1
    release.set()
    first.join(timeout=1.0)
    second.join(timeout=1.0)
    assert not first.is_alive()
    assert not second.is_alive()


def test_runner_merges_explicit_environment_without_enabling_shell() -> None:
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return CompletedProcess(command, 0, stdout="", stderr="")

    executor = BluetoothCommandRunner(
        "pactl",
        runner=runner,
        environment={"PULSE_SERVER": "unix:/run/user/1000/pulse/native"},
    )
    executor.run_args(["info"])

    assert calls[0]["shell"] is False
    assert calls[0]["env"]["PULSE_SERVER"] == "unix:/run/user/1000/pulse/native"


def test_run_args_accepts_a_bounded_command_timeout_override() -> None:
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return CompletedProcess(command, 0, stdout="", stderr="")

    executor = BluetoothCommandRunner("bluetoothctl", runner=runner, timeout=5)
    executor.run_args(["--timeout", "20", "connect", "AA:BB:CC:DD:EE:FF"], timeout=20)

    assert calls[0]["command"] == [
        "bluetoothctl",
        "--timeout",
        "20",
        "connect",
        "AA:BB:CC:DD:EE:FF",
    ]
    assert calls[0]["timeout"] == 20
    assert calls[0]["shell"] is False


def test_run_args_can_use_a_safe_program_override() -> None:
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return CompletedProcess(command, 0, stdout="", stderr="")

    executor = BluetoothCommandRunner("bluetoothctl", runner=runner)
    executor.run_args(["5s", "bluetoothctl", "connect", "AA:BB:CC:DD:EE:FF"], command=("timeout",))

    assert calls[0]["command"] == [
        "timeout",
        "5s",
        "bluetoothctl",
        "connect",
        "AA:BB:CC:DD:EE:FF",
    ]
    assert calls[0]["shell"] is False
