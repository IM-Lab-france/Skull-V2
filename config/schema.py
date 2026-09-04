"""Typed, immutable configuration model for Skull.

Only standard-library modules are used here.  The module is deliberately
side-effect free: loading configuration never imports a hardware client,
opens a socket, or touches a Raspberry Pi.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import ipaddress
import re
from types import MappingProxyType
from typing import Any, Mapping


class ConfigurationError(ValueError):
    """A safe, actionable configuration error without echoed values."""


_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _dns_name(value: str, path: str) -> str:
    if not value:
        return value
    normalized = value.rstrip(".")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        _fail(path, "nom DNS interne attendu, pas une adresse IP ou URL")
    if any(part == "" or not _DNS_LABEL.fullmatch(part) for part in normalized.split(".")):
        _fail(path, "nom DNS interne attendu, pas une adresse IP ou URL")
    return normalized.lower()


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str = "production"
    app_version: str = "dev"


@dataclass(frozen=True)
class HttpConfig:
    bind_host: str = "127.0.0.1"
    port: int = 5000
    request_timeout_s: float = 5.0


@dataclass(frozen=True)
class ServoConfig:
    channel: int
    min_deg: float
    max_deg: float
    neutral_deg: float
    offset_deg: float = 0.0
    enabled: bool = True


@dataclass(frozen=True)
class HardwareConfig:
    pca9685_address: int = 0x40
    frequency_hz: int = 50
    servos: Mapping[str, ServoConfig] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class AudioConfig:
    library_dir: str = "data"
    volume_max: int = 127
    output: str = "local"


@dataclass(frozen=True)
class BluetoothConfig:
    address: str = ""
    name: str = ""
    auto_reconnect: bool = True
    max_attempts: int = 3
    retry_initial_s: float = 1.0
    retry_max_s: float = 30.0
    fallback_output: str = "local"


@dataclass(frozen=True)
class Esp32Config:
    host: str = ""
    port: int = 80
    enabled: bool = False
    fallback_host: str = ""


@dataclass(frozen=True)
class SmokeConfig:
    enabled: bool = False
    endpoint_ref: str = "env:SKULL_SMOKE_WEBHOOK_URL"
    timeout_s: float = 2.0


@dataclass(frozen=True)
class StorageConfig:
    code_dir: str = "/opt/skull/current"
    config_file: str = "/etc/skull/config.toml"
    secrets_file: str = "/etc/skull/secrets.env"
    data_dir: str = "/var/lib/skull"
    log_dir: str = "/var/log/skull"


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    max_bytes: int = 10_485_760
    backup_count: int = 5


@dataclass(frozen=True)
class SecurityConfig:
    allowed_env: tuple[str, ...] = (
        "SKULL_RUNTIME_MODE",
        "SKULL_LOG_LEVEL",
        "SKULL_SMOKE_WEBHOOK_REF",
    )
    redact_configuration: bool = True


@dataclass(frozen=True)
class SkullConfig:
    runtime: RuntimeConfig
    http: HttpConfig
    hardware: HardwareConfig
    audio: AudioConfig
    bluetooth: BluetoothConfig
    esp32: Esp32Config
    smoke: SmokeConfig
    storage: StorageConfig
    logging: LoggingConfig
    security: SecurityConfig

    def redacted_dict(self, *, include_provenance: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic view with secret refs removed."""
        result = {
            "runtime": asdict(self.runtime),
            "http": asdict(self.http),
            "hardware": {
                "pca9685_address": self.hardware.pca9685_address,
                "frequency_hz": self.hardware.frequency_hz,
                "servos": {},
            },
            "audio": asdict(self.audio),
            "bluetooth": asdict(self.bluetooth),
            "esp32": asdict(self.esp32),
            "smoke": asdict(self.smoke),
            "storage": asdict(self.storage),
            "logging": asdict(self.logging),
            "security": asdict(self.security),
        }
        result["hardware"]["servos"] = {
            name: asdict(spec) for name, spec in self.hardware.servos.items()
        }
        result["smoke"]["endpoint_ref"] = "<secret-ref>"
        result["security"]["allowed_env"] = list(self.security.allowed_env)
        if include_provenance is not None:
            result["provenance"] = dict(sorted(include_provenance.items()))
        return result


SERVO_DEFAULTS: dict[str, dict[str, Any]] = {
    "jaw": {"channel": 0, "min_deg": 110.0, "max_deg": 185.0, "neutral_deg": 145.0, "offset_deg": 0.0, "enabled": True},
    "eye_left": {"channel": 1, "min_deg": 60.0, "max_deg": 120.0, "neutral_deg": 90.0, "offset_deg": -14.0, "enabled": True},
    "eye_right": {"channel": 2, "min_deg": 60.0, "max_deg": 120.0, "neutral_deg": 90.0, "offset_deg": 0.0, "enabled": True},
    "neck_pan": {"channel": 3, "min_deg": 0.0, "max_deg": 180.0, "neutral_deg": 90.0, "offset_deg": 0.0, "enabled": True},
}


DEFAULT_RAW: dict[str, Any] = {
    "runtime": {"mode": "production", "app_version": "dev"},
    "http": {"bind_host": "127.0.0.1", "port": 5000, "request_timeout_s": 5.0},
    "hardware": {"pca9685_address": 0x40, "frequency_hz": 50, "servos": SERVO_DEFAULTS},
    "audio": {"library_dir": "data", "volume_max": 127, "output": "local"},
    "bluetooth": {"address": "", "name": "", "auto_reconnect": True, "max_attempts": 3, "retry_initial_s": 1.0, "retry_max_s": 30.0, "fallback_output": "local"},
    "esp32": {"host": "", "port": 80, "enabled": False, "fallback_host": ""},
    "smoke": {"enabled": False, "endpoint_ref": "env:SKULL_SMOKE_WEBHOOK_URL", "timeout_s": 2.0},
    "storage": {"code_dir": "/opt/skull/current", "config_file": "/etc/skull/config.toml", "secrets_file": "/etc/skull/secrets.env", "data_dir": "/var/lib/skull", "log_dir": "/var/log/skull"},
    "logging": {"level": "INFO", "max_bytes": 10_485_760, "backup_count": 5},
    "security": {"allowed_env": ["SKULL_RUNTIME_MODE", "SKULL_LOG_LEVEL", "SKULL_SMOKE_WEBHOOK_REF"], "redact_configuration": True},
}


SECTION_FIELDS: dict[str, set[str]] = {
    section: set(values) for section, values in (
        ("runtime", DEFAULT_RAW["runtime"]),
        ("http", DEFAULT_RAW["http"]),
        ("hardware", {"pca9685_address", "frequency_hz", "servos"}),
        ("audio", DEFAULT_RAW["audio"]),
        ("bluetooth", DEFAULT_RAW["bluetooth"]),
        ("esp32", DEFAULT_RAW["esp32"]),
        ("smoke", DEFAULT_RAW["smoke"]),
        ("storage", DEFAULT_RAW["storage"]),
        ("logging", DEFAULT_RAW["logging"]),
        ("security", DEFAULT_RAW["security"]),
    )
}


def deep_copy_defaults() -> dict[str, Any]:
    return {section: dict(values) for section, values in DEFAULT_RAW.items()}


def _fail(path: str, reason: str) -> None:
    raise ConfigurationError(f"Configuration invalide: {path}: {reason}")


def _string(value: Any, path: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        _fail(path, "texte attendu")
    return value.strip() if path not in {"runtime.app_version", "storage.code_dir", "storage.config_file", "storage.secrets_file", "storage.data_dir", "storage.log_dir", "audio.library_dir"} else value


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "booléen attendu")
    return value


def _int(value: Any, path: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "entier attendu")
    if not low <= value <= high:
        _fail(path, "hors plage")
    return value


def _float(value: Any, path: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "nombre attendu")
    number = float(value)
    if not low <= number <= high:
        _fail(path, "hors plage")
    return number


def _validate_ref(value: Any, path: str) -> str:
    ref = _string(value, path, allow_empty=False)
    if not (ref.startswith("env:") or ref.startswith("file:")):
        _fail(path, "référence env: ou file: attendue")
    if any(char in ref for char in "\r\n"):
        _fail(path, "référence invalide")
    return ref


def validate_raw(raw: Mapping[str, Any]) -> SkullConfig:
    """Validate a merged raw mapping and build immutable typed sections."""
    if set(raw) != set(SECTION_FIELDS):
        unknown = sorted(set(raw) - set(SECTION_FIELDS))
        missing = sorted(set(SECTION_FIELDS) - set(raw))
        _fail(unknown[0] if unknown else missing[0], "section inconnue ou manquante")
    for section, fields in SECTION_FIELDS.items():
        value = raw[section]
        if not isinstance(value, Mapping):
            _fail(section, "tableau TOML attendu")
        unknown = sorted(set(value) - fields)
        if unknown:
            _fail(f"{section}.{unknown[0]}", "clé inconnue")

    runtime = raw["runtime"]
    mode = _string(runtime["mode"], "runtime.mode")
    if mode not in {"production", "simulated"}:
        _fail("runtime.mode", "production ou simulated attendu")
    runtime_cfg = RuntimeConfig(mode, _string(runtime["app_version"], "runtime.app_version"))

    http = raw["http"]
    http_cfg = HttpConfig(_string(http["bind_host"], "http.bind_host", allow_empty=False), _int(http["port"], "http.port", 1, 65535), _float(http["request_timeout_s"], "http.request_timeout_s", 0.1, 60.0))

    hardware = raw["hardware"]
    hardware_cfg = HardwareConfig(_int(hardware["pca9685_address"], "hardware.pca9685_address", 0x03, 0x77), _int(hardware["frequency_hz"], "hardware.frequency_hz", 1, 1000), _validate_servos(hardware["servos"]))

    audio = raw["audio"]
    audio_cfg = AudioConfig(_string(audio["library_dir"], "audio.library_dir", allow_empty=False), _int(audio["volume_max"], "audio.volume_max", 0, 127), _string(audio["output"], "audio.output", allow_empty=False))

    bluetooth = raw["bluetooth"]
    address = _string(bluetooth["address"], "bluetooth.address").upper()
    if address and (len(address) != 17 or any(i not in "0123456789ABCDEF:" for i in address) or address.count(":") != 5):
        _fail("bluetooth.address", "adresse Bluetooth invalide")
    bluetooth_cfg = BluetoothConfig(address, _string(bluetooth["name"], "bluetooth.name"), _bool(bluetooth["auto_reconnect"], "bluetooth.auto_reconnect"), _int(bluetooth["max_attempts"], "bluetooth.max_attempts", 0, 20), _float(bluetooth["retry_initial_s"], "bluetooth.retry_initial_s", 0.0, 3600.0), _float(bluetooth["retry_max_s"], "bluetooth.retry_max_s", 0.0, 3600.0), _string(bluetooth["fallback_output"], "bluetooth.fallback_output", allow_empty=False))
    if bluetooth_cfg.retry_initial_s > bluetooth_cfg.retry_max_s:
        _fail("bluetooth.retry_initial_s", "ne peut pas dépasser retry_max_s")

    esp32 = raw["esp32"]
    esp32_cfg = Esp32Config(_dns_name(_string(esp32["host"], "esp32.host"), "esp32.host"), _int(esp32["port"], "esp32.port", 1, 65535), _bool(esp32["enabled"], "esp32.enabled"), _string(esp32["fallback_host"], "esp32.fallback_host"))
    if esp32_cfg.enabled and not esp32_cfg.host:
        _fail("esp32.host", "obligatoire quand esp32.enabled est vrai")

    smoke = raw["smoke"]
    smoke_cfg = SmokeConfig(_bool(smoke["enabled"], "smoke.enabled"), _validate_ref(smoke["endpoint_ref"], "smoke.endpoint_ref"), _float(smoke["timeout_s"], "smoke.timeout_s", 0.1, 60.0))

    storage = raw["storage"]
    storage_cfg = StorageConfig(*(_string(storage[key], f"storage.{key}", allow_empty=False) for key in ("code_dir", "config_file", "secrets_file", "data_dir", "log_dir")))
    logging = raw["logging"]
    level = _string(logging["level"], "logging.level", allow_empty=False).upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        _fail("logging.level", "niveau inconnu")
    logging_cfg = LoggingConfig(level, _int(logging["max_bytes"], "logging.max_bytes", 1024, 1_000_000_000), _int(logging["backup_count"], "logging.backup_count", 0, 100))
    security = raw["security"]
    env_names = security["allowed_env"]
    if not isinstance(env_names, list) or not all(isinstance(item, str) for item in env_names):
        _fail("security.allowed_env", "liste de textes attendue")
    security_cfg = SecurityConfig(tuple(env_names), _bool(security["redact_configuration"], "security.redact_configuration"))
    return SkullConfig(runtime_cfg, http_cfg, hardware_cfg, audio_cfg, bluetooth_cfg, esp32_cfg, smoke_cfg, storage_cfg, logging_cfg, security_cfg)


def _validate_servos(value: Any) -> Mapping[str, ServoConfig]:
    if not isinstance(value, Mapping):
        _fail("hardware.servos", "tableau attendu")
    result: dict[str, ServoConfig] = {}
    channels: set[int] = set()
    for name, item in value.items():
        path = f"hardware.servos.{name}"
        if not isinstance(name, str) or not isinstance(item, Mapping):
            _fail(path, "servo invalide")
        expected = {"channel", "min_deg", "max_deg", "neutral_deg", "offset_deg", "enabled"}
        unknown = sorted(set(item) - expected)
        if unknown:
            _fail(f"{path}.{unknown[0]}", "clé inconnue")
        channel = _int(item["channel"], f"{path}.channel", 0, 15)
        if channel in channels:
            _fail(f"{path}.channel", "canal déjà utilisé")
        channels.add(channel)
        minimum = _float(item["min_deg"], f"{path}.min_deg", -360.0, 360.0)
        maximum = _float(item["max_deg"], f"{path}.max_deg", -360.0, 360.0)
        neutral = _float(item["neutral_deg"], f"{path}.neutral_deg", -360.0, 360.0)
        if minimum >= maximum:
            _fail(f"{path}.min_deg", "doit être inférieur à max_deg")
        if not minimum <= neutral <= maximum:
            _fail(f"{path}.neutral_deg", "doit être inclus dans les limites")
        result[name] = ServoConfig(channel, minimum, maximum, neutral, _float(item["offset_deg"], f"{path}.offset_deg", -45.0, 45.0), _bool(item["enabled"], f"{path}.enabled"))
    if not result:
        _fail("hardware.servos", "au moins un servo est requis")
    return MappingProxyType(result)


__all__ = ["ConfigurationError", "SkullConfig", "DEFAULT_RAW", "SERVO_DEFAULTS", "deep_copy_defaults", "validate_raw"]
