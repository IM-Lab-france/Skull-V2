"""Read-only conversion of legacy JSON and dotenv configuration to TOML."""

from __future__ import annotations

import json
import ipaddress
from pathlib import Path
from typing import Any

from .schema import ConfigurationError, DEFAULT_RAW, validate_raw


LEGACY_JSON = {
    "channels_state.json": "channels",
    "pitch_offsets.json": "pitch_offsets",
    "esp32_settings.json": "esp32",
    "esp32_button_categories.json": "button_categories",
    "session_categories.json": "session_categories",
}
SERVO_ALIASES = {"neck": "neck_pan"}


def _load_json(path: Path, report: dict[str, Any]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        report.setdefault("errors", []).append(f"{path.name}: lecture JSON impossible")
        return None


def _load_env(path: Path, report: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    except OSError:
        report.setdefault("errors", []).append(f"{path.name}: lecture dotenv impossible")
        return values
    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            report.setdefault("unknown", []).append(f"{path.name}:{line_number}")
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return _toml_bool(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise ConfigurationError("Migration legacy: valeur TOML non supportée")


def _render_toml(raw: dict[str, Any]) -> str:
    lines: list[str] = ["# Candidat généré localement ; ne contient aucun secret.", ""]
    for section in ("runtime", "http", "hardware", "audio", "bluetooth", "esp32", "smoke", "storage", "logging", "security"):
        lines.append(f"[{section}]")
        for key, value in raw[section].items():
            if section == "hardware" and key == "servos":
                continue
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
        if section == "hardware":
            for name in sorted(raw[section]["servos"]):
                lines.append(f"[hardware.servos.{name}]")
                for key, value in raw[section]["servos"][name].items():
                    lines.append(f"{key} = {_toml_value(value)}")
                lines.append("")
    return "\n".join(lines)


def convert_legacy_config(legacy_dir: str | Path, output_path: str | Path, report_path: str | Path | None = None) -> dict[str, Any]:
    """Convert a copy of legacy config without modifying any input or output."""
    source = Path(legacy_dir)
    output = Path(output_path)
    if output.exists():
        raise ConfigurationError("Migration legacy: le fichier cible existe déjà")
    if report_path is not None and Path(report_path).exists():
        raise ConfigurationError("Migration legacy: le rapport cible existe déjà")
    raw = {section: dict(values) for section, values in DEFAULT_RAW.items()}
    report: dict[str, Any] = {"converted": [], "redacted": [], "unknown": [], "blocking": [], "errors": []}

    channels = _load_json(source / "channels_state.json", report)
    if isinstance(channels, dict):
        for name, enabled in channels.items():
            target_name = SERVO_ALIASES.get(name, name)
            if target_name in raw["hardware"]["servos"] and isinstance(enabled, bool):
                raw["hardware"]["servos"][target_name] = dict(raw["hardware"]["servos"][target_name], enabled=enabled)
                report["converted"].append(f"channels.{name}")
            else:
                report["unknown"].append(f"channels.{name}")

    offsets = _load_json(source / "pitch_offsets.json", report)
    if isinstance(offsets, dict):
        for name, offset in offsets.items():
            target_name = SERVO_ALIASES.get(name, name)
            if target_name in raw["hardware"]["servos"] and isinstance(offset, (int, float)) and not isinstance(offset, bool):
                raw["hardware"]["servos"][target_name] = dict(raw["hardware"]["servos"][target_name], offset_deg=float(offset))
                report["converted"].append(f"pitch_offsets.{name}")
            else:
                report["unknown"].append(f"pitch_offsets.{name}")

    esp32 = _load_json(source / "esp32_settings.json", report)
    if isinstance(esp32, dict):
        legacy_ip = False
        for key in ("host", "port", "enabled"):
            if key in esp32:
                if key == "host" and isinstance(esp32[key], str):
                    try:
                        ipaddress.ip_address(esp32[key])
                    except ValueError:
                        raw["esp32"][key] = esp32[key]
                        report["converted"].append("esp32.host")
                    else:
                        legacy_ip = True
                        raw["esp32"]["fallback_host"] = esp32[key]
                        raw["esp32"]["host"] = ""
                        raw["esp32"]["enabled"] = False
                        report["converted"].append("esp32.fallback_host")
                        report["blocking"].append("esp32.host: nom DNS requis avant activation")
                elif key in {"port", "enabled"}:
                    if not (key == "enabled" and legacy_ip):
                        raw["esp32"][key] = esp32[key]
                    report["converted"].append(f"esp32.{key}")
                else:
                    report["unknown"].append(f"esp32.{key}")
        report["unknown"].extend(f"esp32.{key}" for key in sorted(set(esp32) - {"host", "port", "enabled"}))

    for filename, namespace in (("esp32_button_categories.json", "button_categories"), ("session_categories.json", "session_categories")):
        legacy = _load_json(source / filename, report)
        if legacy is not None:
            report["blocking"].append(f"{namespace}: destination absente du schéma phase 8")

    env = _load_env(source / "bluetooth_device.env", report)
    env.update(_load_env(source / ".env", report))
    if "PLAYLIST_BT_DEVICE_ADDR" in env:
        raw["bluetooth"]["address"] = env["PLAYLIST_BT_DEVICE_ADDR"]
        report["converted"].append("bluetooth.address")
    if "PLAYLIST_BT_DEVICE_NAME" in env:
        raw["bluetooth"]["name"] = env["PLAYLIST_BT_DEVICE_NAME"]
        report["converted"].append("bluetooth.name")
    if "SKULL_SMOKE_WEBHOOK_URL" in env or "PLAYLIST_ACCUEIL_WEBHOOK" in env:
        raw["smoke"]["endpoint_ref"] = "env:SKULL_SMOKE_WEBHOOK_URL"
        report["redacted"].append("smoke.endpoint_ref")

    validate_raw(raw)
    report["converted"].sort()
    report["redacted"].sort()
    report["unknown"].sort()
    report["blocking"].sort()
    report["errors"].sort()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_toml(raw), encoding="utf-8", newline="\n")
    if report_path is not None:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


__all__ = ["convert_legacy_config"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convertir une copie de configuration Skull legacy")
    parser.add_argument("legacy_dir", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert_legacy_config(args.legacy_dir, args.output_path, args.report), ensure_ascii=False, indent=2, sort_keys=True))
