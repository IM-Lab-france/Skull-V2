"""Sentinelles de sécurité pour le profil de test."""

from __future__ import annotations

import os


PRODUCTION_MODE_VALUES = {"1", "true", "yes", "on", "production", "prod", "live"}
MODE_VARIABLES = (
    "SKULL_ENV",
    "SKULL_MODE",
    "SKULL_PRODUCTION",
    "FLASK_ENV",
    "ENV",
    "PLAYLIST_ENV",
)


def test_production_mode_is_not_enabled() -> None:
    enabled = {
        name: os.environ.get(name, "").strip().lower()
        for name in MODE_VARIABLES
        if os.environ.get(name, "").strip().lower() in PRODUCTION_MODE_VALUES
    }
    assert not enabled, (
        "Le profil de test ne doit pas être exécuté en mode production : "
        + ", ".join(f"{name}={value!r}" for name, value in enabled.items())
    )


def test_hardware_modules_are_not_imported() -> None:
    import sys

    forbidden = ("board", "busio", "adafruit_pca9685")
    imported = sorted(
        name
        for name in sys.modules
        if name in forbidden or name.startswith(tuple(f"{item}." for item in forbidden))
    )
    assert not imported, f"Modules matériel importés pendant la collecte : {imported}"
