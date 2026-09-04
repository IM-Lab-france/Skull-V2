"""Configuration loading, precedence and secret-free diagnostics."""

from __future__ import annotations

import copy
import os
import tomllib
from pathlib import Path
from typing import Any, Mapping

from .schema import ConfigurationError, SkullConfig, deep_copy_defaults, validate_raw


DEFAULT_CONFIG_PATH = Path("/etc/skull/config.toml")
# Highest priority first.  This is the only precedence rule for the typed
# configuration; legacy modules remain compatibility consumers until migration.
CONFIG_PRECEDENCE = (
    "maintenance_args",
    "environment",
    "toml_file",
    "safe_defaults",
)
ENV_FIELDS: dict[str, tuple[str, str]] = {
    # Legacy alias is accepted during coexistence; the new name below wins
    # deterministically when both are present in the same environment.
    "SKULL_HARDWARE_MODE": ("runtime.mode", "mode"),
    "SKULL_RUNTIME_MODE": ("runtime.mode", "mode"),
    "SKULL_APP_VERSION": ("runtime.app_version", "text"),
    "SKULL_HTTP_BIND_HOST": ("http.bind_host", "text"),
    "SKULL_HTTP_PORT": ("http.port", "int"),
    "SKULL_HARDWARE_I2C_ADDRESS": ("hardware.pca9685_address", "int"),
    "SKULL_HARDWARE_FREQUENCY_HZ": ("hardware.frequency_hz", "int"),
    "SKULL_AUDIO_LIBRARY_DIR": ("audio.library_dir", "text"),
    "SKULL_AUDIO_VOLUME_MAX": ("audio.volume_max", "int"),
    "SKULL_BLUETOOTH_ADDRESS": ("bluetooth.address", "text"),
    "SKULL_BLUETOOTH_AUTO_RECONNECT": ("bluetooth.auto_reconnect", "bool"),
    "SKULL_BLUETOOTH_MAX_ATTEMPTS": ("bluetooth.max_attempts", "int"),
    "SKULL_ESP32_HOST": ("esp32.host", "text"),
    "SKULL_ESP32_PORT": ("esp32.port", "int"),
    "SKULL_ESP32_ENABLED": ("esp32.enabled", "bool"),
    "SKULL_SMOKE_ENABLED": ("smoke.enabled", "bool"),
    "SKULL_SMOKE_WEBHOOK_REF": ("smoke.endpoint_ref", "text"),
    "SKULL_LOG_LEVEL": ("logging.level", "text"),
}
ARG_FIELDS = {"runtime.mode", "logging.level"}


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    section, key = path.split(".", 1)
    target.setdefault(section, {})[key] = value


def _get_path(target: Mapping[str, Any], path: str) -> Any:
    section, key = path.split(".", 1)
    return target[section][key]


def _merge_file(raw: dict[str, Any], document: Mapping[str, Any], provenance: dict[str, str]) -> None:
    allowed_sections = set(raw)
    unknown_sections = sorted(set(document) - allowed_sections)
    if unknown_sections:
        raise ConfigurationError(f"Configuration invalide: {unknown_sections[0]}: section inconnue")
    for section, values in document.items():
        if not isinstance(values, Mapping):
            raise ConfigurationError(f"Configuration invalide: {section}: tableau TOML attendu")
        for key, value in values.items():
            if key == "servos" and section == "hardware":
                if not isinstance(value, Mapping):
                    raise ConfigurationError("Configuration invalide: hardware.servos: tableau attendu")
                merged_servos = copy.deepcopy(raw[section][key])
                for servo_name, servo_values in value.items():
                    if not isinstance(servo_values, Mapping):
                        raise ConfigurationError(f"Configuration invalide: hardware.servos.{servo_name}: tableau attendu")
                    if servo_name not in merged_servos:
                        merged_servos[servo_name] = copy.deepcopy(servo_values)
                    else:
                        merged_servos[servo_name].update(copy.deepcopy(servo_values))
                    for servo_key in servo_values:
                        provenance[f"hardware.servos.{servo_name}.{servo_key}"] = "file"
                raw[section][key] = merged_servos
            elif key not in raw[section]:
                raise ConfigurationError(f"Configuration invalide: {section}.{key}: clé inconnue")
            else:
                raw[section][key] = copy.deepcopy(value)
                provenance[f"{section}.{key}"] = "file"


def _parse_env(name: str, value: str, kind: str) -> Any:
    if kind == "text" or kind == "mode":
        return value
    if kind == "int":
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ConfigurationError(f"Configuration invalide: {name}: entier attendu") from exc
    if kind == "bool":
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ConfigurationError(f"Configuration invalide: {name}: booléen attendu")
    raise ConfigurationError(f"Configuration invalide: {name}: type non supporté")


def load_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    maintenance_args: Mapping[str, Any] | None = None,
) -> tuple[SkullConfig, dict[str, str]]:
    """Load using args > explicit env > TOML file > safe defaults.

    ``maintenance_args`` is intentionally narrow and is not an HTTP input.
    Missing files are allowed so local validation can use safe defaults; a
    path explicitly supplied by the caller must exist.
    """
    env = dict(os.environ if environ is None else environ)
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    raw = deep_copy_defaults()
    provenance = {f"{section}.{key}": "default" for section, values in raw.items() for key in values}
    if config_path.exists():
        try:
            document = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigurationError("Configuration invalide: fichier illisible") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationError("Configuration invalide: TOML illisible") from exc
        _merge_file(raw, document, provenance)
    elif path is not None:
        raise ConfigurationError("Configuration invalide: fichier absent")

    for name, (key, kind) in ENV_FIELDS.items():
        if name in env:
            _set_path(raw, key, _parse_env(name, env[name], kind))
            provenance[key] = f"env:{name}"
    if maintenance_args:
        for key, value in maintenance_args.items():
            if key not in ARG_FIELDS:
                raise ConfigurationError(f"Configuration invalide: {key}: argument de maintenance interdit")
            _set_path(raw, key, value)
            provenance[key] = "argument-maintenance"
    return validate_raw(raw), provenance


__all__ = ["CONFIG_PRECEDENCE", "DEFAULT_CONFIG_PATH", "ENV_FIELDS", "load_config"]
