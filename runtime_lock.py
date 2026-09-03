"""Bounded cross-process lock for the Skull hardware runtime."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional


class RuntimeLockError(RuntimeError):
    """Raised when the hardware runtime lock cannot be acquired in time."""


class RuntimeProcessLock:
    """Hold an exclusive lock file for the lifetime of one runtime process.

    The lock is deliberately bounded: a second process fails predictably
    instead of waiting forever while another process may own the PCA9685.
    ``fcntl`` is used on Linux and ``msvcrt`` on Windows test hosts.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeout: float = 2.0,
        poll_interval: float = 0.05,
    ) -> None:
        self.path = Path(path)
        self.timeout = max(0.0, float(timeout))
        self.poll_interval = max(0.001, float(poll_interval))
        self._fd: Optional[int] = None
        self._backend: Optional[str] = None

    def acquire(self) -> None:
        if self._fd is not None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o660)
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                if self._try_lock(fd):
                    self._fd = fd
                    return
                if time.monotonic() >= deadline:
                    raise RuntimeLockError(
                        f"runtime lock unavailable: {self.path}"
                    )
                time.sleep(self.poll_interval)
        except Exception:
            os.close(fd)
            raise

    def _try_lock(self, fd: int) -> bool:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                return False
            self._backend = "msvcrt"
            return True

        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        self._backend = "fcntl"
        return True

    def release(self) -> None:
        fd = self._fd
        if fd is None:
            return
        try:
            if self._backend == "msvcrt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            elif self._backend == "fcntl":
                import fcntl

                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(fd)
            self._fd = None
            self._backend = None

    def __enter__(self) -> "RuntimeProcessLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()


__all__ = ["RuntimeLockError", "RuntimeProcessLock"]
