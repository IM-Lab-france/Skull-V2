"""No-UDP gaze adapter used by the explicit simulated runtime."""

from __future__ import annotations

from typing import Any


class SimulatedGazeAdapter:
    """In-memory implementation of the small ``GazeAdapter`` boundary."""

    def __init__(self) -> None:
        self.command: dict[str, Any] | None = None
        self.calls: list[tuple[Any, ...]] = []

    def get_command(self) -> dict[str, Any] | None:
        self.calls.append(("get_command",))
        return self.command

    def stop(self, timeout: float = 1.0) -> None:
        self.calls.append(("stop", timeout))


__all__ = ["SimulatedGazeAdapter"]
