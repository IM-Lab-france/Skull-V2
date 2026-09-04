from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from runtime_lock import RuntimeLockError, RuntimeProcessLock
from config.schema import ConfigurationError


def fresh_web_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delitem(sys.modules, "web_app", raising=False)
    import web_app

    return web_app


def test_import_does_not_construct_runtime_or_start_threads(tmp_path: Path) -> None:
    script = """
import json
import threading
import web_app
print(json.dumps({
    'initialized': web_app._runtime_initialized,
    'threads': threading.active_count(),
    'player_proxy': type(web_app.player).__name__,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"PATH": str(Path(sys.executable).parent), "PYTHONPATH": str(Path(__file__).parents[2])},
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"initialized": false' in result.stdout
    assert '"player_proxy": "_LazyRuntimeComponent"' in result.stdout


def test_main_forces_debug_off_and_reloader_off(monkeypatch: pytest.MonkeyPatch) -> None:
    web_app = fresh_web_app(monkeypatch)

    run_options: dict[str, object] = {}
    monkeypatch.setattr(web_app, "initialize_runtime", lambda **kwargs: run_options.update(kwargs))
    monkeypatch.setattr(web_app, "_install_shutdown_handlers", lambda: None)
    monkeypatch.setattr(web_app.app, "run", lambda **kwargs: run_options.update(kwargs))

    web_app.main()

    assert run_options["acquire_process_lock"] is True
    assert run_options["debug"] is False
    assert run_options["use_reloader"] is False


def test_invalid_typed_configuration_blocks_hardware_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_app = fresh_web_app(monkeypatch)
    constructed: list[str] = []

    def reject_configuration():
        raise ConfigurationError(
            "Configuration invalide: hardware.frequency_hz: hors plage"
        )

    monkeypatch.setattr(web_app, "load_config", reject_configuration)

    class FakePlayer:
        def __init__(self) -> None:
            constructed.append("player")

    class FakeLoopPlayer:
        def __init__(self, _storage_dir) -> None:
            constructed.append("loop")

    with pytest.raises(ConfigurationError, match="hardware.frequency_hz"):
        web_app.initialize_runtime(
            sync_player_cls=FakePlayer,
            loop_player_cls=FakeLoopPlayer,
        )

    assert constructed == []
    assert web_app._runtime_initialized is False


def test_simulated_concurrent_initialization_constructs_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_app = fresh_web_app(monkeypatch)

    monkeypatch.setenv("SKULL_HARDWARE_MODE", "simulated")
    constructed: list[str] = []

    class FakePlayer:
        def __init__(self) -> None:
            constructed.append("player")
            time.sleep(0.02)

        def set_on_track_finished(self, callback) -> None:
            self.callback = callback

        def cleanup(self) -> None:
            constructed.append("player-cleanup")

    class FakeLoopPlayer:
        def __init__(self, _storage_dir) -> None:
            constructed.append("loop")

        def stop(self) -> None:
            constructed.append("loop-stop")

    results = []
    errors = []

    def start() -> None:
        try:
            results.append(
                web_app.initialize_runtime(
                    sync_player_cls=FakePlayer,
                    loop_player_cls=FakeLoopPlayer,
                )
            )
        except Exception as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    first = threading.Thread(target=start)
    second = threading.Thread(target=start)
    first.start()
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert constructed.count("player") == 1
    assert constructed.count("loop") == 1

    web_app.cleanup_runtime()
    web_app.cleanup_runtime()
    assert constructed.count("player-cleanup") == 1
    assert constructed.count("loop-stop") == 1


def test_process_lock_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "runtime.lock"
    first = RuntimeProcessLock(path, timeout=0.1, poll_interval=0.01)
    second = RuntimeProcessLock(path, timeout=0.05, poll_interval=0.01)
    first.acquire()
    try:
        with pytest.raises(RuntimeLockError):
            second.acquire()
    finally:
        first.release()
        second.release()
