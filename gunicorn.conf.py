"""Single-worker Gunicorn configuration for the Skull WSGI candidate."""

from __future__ import annotations

import os


bind = os.environ.get("SKULL_WSGI_BIND", "127.0.0.1:5002")
workers = 1
threads = 1
worker_class = "sync"
preload_app = False
timeout = int(os.environ.get("SKULL_WSGI_TIMEOUT", "30"))
graceful_timeout = int(os.environ.get("SKULL_WSGI_GRACEFUL_TIMEOUT", "10"))
accesslog = "-"
errorlog = "-"
loglevel = "info"


def _cleanup_runtime() -> None:
    import web_app

    web_app.cleanup_runtime()


def post_worker_init(worker) -> None:
    """Initialize real hardware after the single worker has been forked."""
    if os.environ.get("SKULL_HARDWARE_MODE") == "simulated":
        return
    import web_app

    web_app.initialize_runtime(acquire_process_lock=True)


def worker_int(worker) -> None:
    _cleanup_runtime()


def worker_exit(server, worker) -> None:
    _cleanup_runtime()
