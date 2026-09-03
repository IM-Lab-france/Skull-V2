"""Bounded, serialized command execution for Bluetooth control tools."""

from __future__ import annotations

from contextlib import contextmanager
import os
import re
import subprocess
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence


Runner = Callable[..., subprocess.CompletedProcess[str]]


class BluetoothCommandRunner:
    """Run interactive Bluetooth tools without a shell or unbounded output."""

    _operation_lock = threading.RLock()
    _ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    _credential_re = re.compile(
        r"(?i)(https?://)([^/\s:@]+):([^@\s/]+)@",
    )
    _secret_re = re.compile(
        r"(?i)\b(token|secret|password|passwd|api[_-]?key)(\s*[=:]\s*)[^\s,;]+",
    )

    def __init__(
        self,
        command: Sequence[str] | str,
        *,
        runner: Runner | None = None,
        timeout: float = 5.0,
        output_limit: int = 4096,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if isinstance(command, str):
            command = (command,)
        self.command = tuple(str(part) for part in command if str(part))
        if not self.command:
            raise ValueError("Commande vide")
        self.runner = runner
        self.timeout = max(0.1, float(timeout))
        self.output_limit = max(256, int(output_limit))
        self.environment = dict(environment) if environment else None

    def _environment(self) -> dict[str, str] | None:
        if self.environment is None:
            return None
        environment = os.environ.copy()
        environment.update(self.environment)
        return environment

    @classmethod
    def _normalize_output(cls, value: object, limit: int) -> str:
        if isinstance(value, bytes):
            text = value.decode("utf-8", errors="replace")
        else:
            text = str(value or "")
        text = cls._ansi_re.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
        text = cls._credential_re.sub(r"\1<redacted>@", text)
        text = cls._secret_re.sub(r"\1\2<redacted>", text)
        return text[:limit]

    @staticmethod
    def _validate_commands(commands: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(str(command) for command in commands if str(command).strip())
        if not normalized:
            raise ValueError("Commande vide")
        if any("\r" in command or "\n" in command for command in normalized):
            raise ValueError("Commande Bluetooth invalide")
        return normalized

    @contextmanager
    def operation(self) -> Iterator[None]:
        """Serialize one multi-command operation across all runner instances."""
        with self._operation_lock:
            yield

    def run(self, commands: Sequence[str]) -> subprocess.CompletedProcess[str]:
        normalized = self._validate_commands(commands)
        effective = list(normalized)
        if effective[0].startswith("menu "):
            effective.append("back")
        effective.append("quit")
        script = "\n".join(effective) + "\n"
        runner = self.runner or subprocess.run
        kwargs = {
            "input": script,
            "check": False,
            "capture_output": True,
            "text": True,
            "shell": False,
            "timeout": self.timeout,
        }
        environment = self._environment()
        if environment is not None:
            kwargs["env"] = environment
        with self._operation_lock:
            result = runner(list(self.command), **kwargs)
        result.stdout = self._normalize_output(result.stdout, self.output_limit)
        result.stderr = self._normalize_output(result.stderr, self.output_limit)
        return result

    def run_args(
        self,
        arguments: Sequence[str],
        *,
        timeout: float | None = None,
        command: Sequence[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a non-interactive command with the same safety guarantees."""
        normalized = self._validate_commands(arguments)
        program = self.command if command is None else tuple(str(part) for part in command if str(part))
        if not program:
            raise ValueError("Commande vide")
        runner = self.runner or subprocess.run
        kwargs = {
            "check": False,
            "capture_output": True,
            "text": True,
            "shell": False,
            "timeout": self.timeout if timeout is None else max(0.1, float(timeout)),
        }
        environment = self._environment()
        if environment is not None:
            kwargs["env"] = environment
        with self._operation_lock:
            result = runner([*program, *normalized], **kwargs)
        result.stdout = self._normalize_output(result.stdout, self.output_limit)
        result.stderr = self._normalize_output(result.stderr, self.output_limit)
        return result


__all__ = ["BluetoothCommandRunner"]
