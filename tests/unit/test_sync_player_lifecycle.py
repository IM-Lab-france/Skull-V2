from __future__ import annotations

import sys
import threading
import time
import types
from pathlib import Path

import pytest

from domain.models import PlaybackState


class FakePlayObject:
    def __init__(self) -> None:
        self.stopped = threading.Event()

    def stop(self) -> None:
        self.stopped.set()

    def wait_done(self) -> None:
        self.stopped.wait(0.5)


class FakeHardware:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.neutral_calls = 0

    def set_named_angle(self, *args, **kwargs) -> None:
        if self.fail:
            raise RuntimeError("synthetic servo failure")

    def neutral(self) -> None:
        self.neutral_calls += 1


class FakeGaze:
    def get_command(self):
        return None


class FakeLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def load_sync_player(monkeypatch: pytest.MonkeyPatch):
    fake_rpi = types.ModuleType("rpi_hardware")
    fake_rpi.Hardware = FakeHardware
    fake_sa = types.ModuleType("simpleaudio")
    fake_sa.play_buffer = lambda *args, **kwargs: FakePlayObject()
    fake_pydub = types.ModuleType("pydub")
    fake_pydub.AudioSegment = object
    fake_gaze = types.ModuleType("gaze_receiver")
    fake_gaze.GazeReceiver = FakeGaze
    fake_logger = types.ModuleType("logger")
    fake_logger.servo_logger = types.SimpleNamespace(
        logger=FakeLogger(),
        start_session=lambda *args, **kwargs: None,
        start_audio=lambda *args, **kwargs: None,
        log_audio_end=lambda *args, **kwargs: None,
        end_session=lambda *args, **kwargs: None,
        log_servo_command=lambda *args, **kwargs: None,
    )
    for name, module in {
        "rpi_hardware": fake_rpi,
        "simpleaudio": fake_sa,
        "pydub": fake_pydub,
        "gaze_receiver": fake_gaze,
        "logger": fake_logger,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules.pop("sync_player", None)
    import sync_player

    return sync_player.SyncPlayer


def make_player(sync_player_cls, *, fail: bool = False):
    player = sync_player_cls.__new__(sync_player_cls)
    player.hw = FakeHardware(fail=fail)
    player.timeline = types.SimpleNamespace(
        frames=[
            {
                "timestamp_ms": 60_000,
                "jaw_deg": 130.0,
                "neck_pan_deg": 90.0,
                "eye_left_deg": 90.0,
                "eye_right_deg": 90.0,
            }
        ]
    )
    player.audio = types.SimpleNamespace(
        raw_data=b"synthetic",
        channels=2,
        sample_width=2,
        frame_rate=8000,
    )
    player._play_obj = None
    player._thread = None
    player._running = threading.Event()
    player._paused = threading.Event()
    player._stop_event = threading.Event()
    player._lock = threading.Lock()
    player.state_machine = __import__(
        "domain.state_machine", fromlist=["PlaybackStateMachine"]
    ).PlaybackStateMachine()
    player.session_dir = Path("synthetic")
    player._start_time = 0.0
    player._pause_pos_ms = 0
    player.channels = {"eye_left": True, "eye_right": True, "neck": True, "jaw": True}
    player._last_target = {
        "jaw": 130.0,
        "neck": 90.0,
        "eye_left": 90.0,
        "eye_right": 90.0,
    }
    player.track_enable = False
    player.gaze = FakeGaze()
    player._on_track_finished = None
    player._stop_reason = None
    return player


def start_runner(player, *, expect_running: bool = True) -> threading.Thread:
    player._stop_event.clear()
    player.state_machine.transition("start")
    thread = threading.Thread(target=player._runner, daemon=True)
    player._thread = thread
    thread.start()
    if expect_running:
        deadline = time.monotonic() + 1.0
        while not player._running.is_set() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert player._running.is_set()
    return thread


def test_stop_interrupts_waiting_worker_and_leaves_no_orphan_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_player_cls = load_sync_player(monkeypatch)
    player = make_player(sync_player_cls)
    thread = start_runner(player)

    player.stop(reason="test")

    assert not thread.is_alive()
    assert player.state_machine.state is PlaybackState.IDLE
    assert player.hw.neutral_calls >= 1


def test_worker_error_reaches_error_state_after_safe_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_player_cls = load_sync_player(monkeypatch)
    player = make_player(sync_player_cls, fail=True)
    player.timeline.frames[0]["timestamp_ms"] = 0
    thread = start_runner(player, expect_running=False)
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert player.state_machine.state is PlaybackState.ERROR
    assert player.hw.neutral_calls == 1
