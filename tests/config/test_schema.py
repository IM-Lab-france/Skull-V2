from __future__ import annotations

import copy

import pytest

from config.loader import CONFIG_PRECEDENCE, load_config
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


def test_precedence_constant_and_all_source_collisions(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[runtime]\napp_version = "from-file"\n'
        '[http]\nport = 5100\n'
        '[logging]\nlevel = "WARNING"\n',
        encoding="utf-8",
    )

    config, provenance = load_config(
        path,
        environ={
            "SKULL_APP_VERSION": "from-environment",
            "SKULL_HTTP_PORT": "5200",
            "SKULL_LOG_LEVEL": "ERROR",
        },
        maintenance_args={"logging.level": "DEBUG"},
    )

    assert CONFIG_PRECEDENCE == (
        "maintenance_args",
        "environment",
        "toml_file",
        "safe_defaults",
    )
    assert config.runtime.app_version == "from-environment"
    assert config.http.port == 5200
    assert config.logging.level == "DEBUG"
    assert provenance["runtime.app_version"] == "env:SKULL_APP_VERSION"
    assert provenance["http.port"] == "env:SKULL_HTTP_PORT"
    assert provenance["logging.level"] == "argument-maintenance"


def test_new_runtime_mode_environment_name_wins_over_legacy_alias() -> None:
    config, provenance = load_config(
        environ={
            "SKULL_HARDWARE_MODE": "simulated",
            "SKULL_RUNTIME_MODE": "production",
        }
    )

    assert config.runtime.mode == "production"
    assert provenance["runtime.mode"] == "env:SKULL_RUNTIME_MODE"


def test_default_config_loading_is_not_dependent_on_current_directory(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config, provenance = load_config(environ={})

    assert config.runtime.mode == "production"
    assert provenance["runtime.mode"] == "default"


def test_maintenance_args_cannot_change_hardware(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="argument de maintenance interdit"):
        load_config(environ={}, maintenance_args={"hardware.frequency_hz": 400})


def test_esp32_rejects_literal_ip_in_primary_endpoint(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[esp32]\nhost = "192.0.2.10"\n', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="esp32.host"):
        load_config(path, environ={})
