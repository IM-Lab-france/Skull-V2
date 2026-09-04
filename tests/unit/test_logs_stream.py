from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest


def test_logs_stream_is_bounded_and_emits_sse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKULL_SMOKE_WEBHOOK_URL", "")
    sys.modules.pop("web_app", None)
    import web_app

    log_file = tmp_path / "runtime.log"
    log_file.write_text("existing\n", encoding="utf-8")
    monkeypatch.setattr(web_app.servo_logger, "get_latest_log_file", lambda: log_file)
    monkeypatch.setattr(web_app, "LOG_STREAM_WINDOW_SECONDS", 0.1)
    monkeypatch.setattr(web_app, "LOG_STREAM_POLL_INTERVAL", 0.01)

    started = time.monotonic()
    response = web_app.app.test_client().get("/logs/stream", buffered=False)
    chunks = list(response.response)
    elapsed = time.monotonic() - started
    body = b"".join(chunks)

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert b": keep-alive" in body
    assert b"retry: 1000" in body
    assert elapsed < 1.0
