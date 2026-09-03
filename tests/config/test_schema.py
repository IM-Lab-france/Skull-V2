from __future__ import annotations

import copy

import pytest

from config.loader import load_config
from config.schema import ConfigurationError, DEFAULT_RAW, validate_raw


def test_minimal_defaults_are_typed_and_immutable() -> None:
    config, provenance = load_config(environ={})
    assert config.runtime.mode == "production"
    assert config.hardware.servos["jaw"].channel == 0
    assert provenance["runtime.mode"] == "default"
    with pytest.raises(AttributeError):
        config.runtime.mode = "simulated"


def test_complete_toml_is_loaded_and_redacted(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[smoke]\nenabled = true\nendpoint_ref = "env:TEST_WEBHOOK"\ntimeout_s = 3.0\n', encoding="utf-8")
    config, provenance = load_config(path, environ={})
    assert config.smoke.enabled is True
    assert config.redacted_dict(include_provenance=provenance)["smoke"]["endpoint_ref"] == "<secret-ref>"
    assert provenance["smoke.endpoint_ref"] == "file"


def test_partial_servo_override_keeps_other_safe_defaults(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[hardware.servos.jaw]\noffset_deg = 3.0\n", encoding="utf-8")
    config, provenance = load_config(path, environ={})
    assert len(config.hardware.servos) == 4
    assert config.hardware.servos["jaw"].offset_deg == 3.0
    assert config.hardware.servos["jaw"].min_deg == 110.0
    assert provenance["hardware.servos.jaw.offset_deg"] == "file"


@pytest.mark.parametrize(
    ("section", "key", "value", "needle"),
    [
        ("http", "port", 0, "http.port"),
        ("hardware", "frequency_hz", 0, "hardware.frequency_hz"),
        ("logging", "level", "TRACE", "logging.level"),
    ],
)
def test_invalid_values_report_precise_path(section, key, value, needle) -> None:
    raw = copy.deepcopy(DEFAULT_RAW)
    raw[section][key] = value
    with pytest.raises(ConfigurationError, match=needle):
        validate_raw(raw)


def test_unknown_key_and_cross_section_constraint_fail(tmp_path) -> None:
    unknown = tmp_path / "unknown.toml"
    unknown.write_text("[runtime]\nunknown = true\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="runtime.unknown"):
        load_config(unknown, environ={})

    raw = copy.deepcopy(DEFAULT_RAW)
    raw["hardware"]["servos"]["jaw"]["neutral_deg"] = 999
    with pytest.raises(ConfigurationError, match="hardware.servos.jaw.neutral_deg"):
        validate_raw(raw)


def test_precedence_is_args_then_environment_then_file_then_defaults(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[runtime]\nmode = "production"\n', encoding="utf-8")
    config, provenance = load_config(path, environ={"SKULL_RUNTIME_MODE": "simulated"}, maintenance_args={"runtime.mode": "production"})
    assert config.runtime.mode == "production"
    assert provenance["runtime.mode"] == "argument-maintenance"


def test_maintenance_args_cannot_change_hardware(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="argument de maintenance interdit"):
        load_config(environ={}, maintenance_args={"hardware.frequency_hz": 400})
