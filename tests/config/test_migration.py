from __future__ import annotations

import json

import pytest

from config.migrate_legacy import convert_legacy_config
from config.schema import ConfigurationError


def _legacy_fixture(path) -> None:
    (path / "channels_state.json").write_text(json.dumps({"jaw": False}), encoding="utf-8")
    (path / "pitch_offsets.json").write_text(json.dumps({"jaw": 2.0}), encoding="utf-8")
    (path / "esp32_settings.json").write_text(json.dumps({"host": "esp32-boutons.home.arpa", "port": 80, "enabled": True}), encoding="utf-8")
    (path / "bluetooth_device.env").write_text("PLAYLIST_BT_DEVICE_ADDR=00:00:00:00:00:00\nSKULL_SMOKE_WEBHOOK_URL=DO_NOT_COPY\n", encoding="utf-8")


def test_conversion_is_read_only_deterministic_and_redacts_secret(tmp_path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    _legacy_fixture(source)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    first = tmp_path / "first.toml"
    first_report = tmp_path / "first.json"
    report = convert_legacy_config(source, first, first_report)
    second = tmp_path / "second.toml"
    second_report = tmp_path / "second.json"
    convert_legacy_config(source, second, second_report)
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert first_report.read_text(encoding="utf-8") == second_report.read_text(encoding="utf-8")
    assert "DO_NOT_COPY" not in first.read_text(encoding="utf-8")
    assert "DO_NOT_COPY" not in first_report.read_text(encoding="utf-8")
    assert "smoke.endpoint_ref" in report["redacted"]
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_conversion_does_not_overwrite_existing_target(tmp_path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    target = tmp_path / "candidate.toml"
    target.write_text("keep", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="existe déjà"):
        convert_legacy_config(source, target)
    assert target.read_text(encoding="utf-8") == "keep"
