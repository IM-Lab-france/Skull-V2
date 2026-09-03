"""Injectable clocks used by deterministic local simulations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Minimal clock boundary required by the simulated audio player."""

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SimulatedClock:
    """Monotonic clock whose time advances only when explicitly requested.

    ``sleep`` has the same validation intent as ``time.sleep`` but does not
    block.  ``advance`` is the test-driver operation used to move playback
    forward deterministically.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        self.sleep_calls.append(seconds)
        self._now += seconds

    def advance(self, seconds: float) -> None:
        """Advance logical time without waiting for wall-clock time."""
        self.sleep(seconds)

    def reset(self, value: float = 0.0) -> None:
        """Reset the logical clock and clear its sleep history."""
        self._now = float(value)
        self.sleep_calls.clear()


__all__ = ["Clock", "SimulatedClock"]
