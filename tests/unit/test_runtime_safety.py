from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from logger import ServoLogger


ROOT = Path(__file__).parents[2]


def _external_calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            owner = ast.unparse(node.func.value)
            name = node.func.attr
        else:
            owner = ""
            name = ast.unparse(node.func)
        if (
            (owner == "subprocess" and name == "run")
            or (owner == "requests" and name in {"get", "post", "request"})
            or (owner == "" and name == "urlopen")
        ):
            yield node, owner, name


@pytest.mark.parametrize("filename", ["web_app.py", "playlist_web.py"])
def test_external_calls_declare_a_timeout(filename: str) -> None:
    missing = []
    for node, owner, name in _external_calls(ROOT / filename):
        keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
        if "timeout" not in keywords:
            missing.append(f"{filename}:{node.lineno} {owner}.{name}")
    assert missing == []


def test_bluetooth_connection_is_not_a_systemd_startup_precondition() -> None:
    service_template = (ROOT / "install_skull.sh").read_text(encoding="utf-8")
    assert "ExecStartPre" in service_template
    assert "bluetoothctl connect" not in service_template.split("write_systemd_service()", 1)[1]


def test_log_rotation_and_retention_bound_disk_growth(tmp_path: Path) -> None:
    logger = ServoLogger(
        tmp_path / "logs",
        max_bytes=128,
        backup_count=2,
        stats_retention=2,
        logger_name="test_runtime_safety_rotation",
    )

    for index in range(20):
        logger.logger.info("x" * 80 + " %s", index)

    log_files = sorted((tmp_path / "logs").glob("servo_commands_*.log*"))
    assert len(log_files) <= 3
    assert sum(path.stat().st_size for path in log_files) <= 3 * 128 + 3 * 80

    for index in range(4):
        stats_file = tmp_path / "logs" / f"session_stats_20260903_00000{index}.json"
        stats_file.write_text("{}", encoding="utf-8")
        os.utime(stats_file, (index, index))
    logger._prune_session_stats()
    assert len(list((tmp_path / "logs").glob("session_stats_*.json"))) == 2


def test_unavailable_log_directory_does_not_abort_runtime(monkeypatch, tmp_path: Path) -> None:
    original_mkdir = Path.mkdir

    def unavailable(self: Path, *args, **kwargs):
        if self == tmp_path / "unavailable":
            raise OSError("synthetic log disk unavailable")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", unavailable)
    logger = ServoLogger(
        tmp_path / "unavailable",
        logger_name="test_runtime_safety_unavailable",
    )

    logger.start_session("synthetic", 0.1)
    logger.end_session()
    assert logger.storage_available is False


def test_log_permissions_are_declared_for_production() -> None:
    installer = (ROOT / "install_skull.sh").read_text(encoding="utf-8")
    assert "install -d -m 0750" in installer
    assert "chmod 0640" in installer
