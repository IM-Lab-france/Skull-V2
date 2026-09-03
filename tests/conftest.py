"""Garde-fous communs pour la collecte locale sans matériel."""

from __future__ import annotations

import sys


FORBIDDEN_HARDWARE_MODULES = {
    "board",
    "busio",
    "adafruit_pca9685",
    "adafruit_pca9685.pca9685",
}


def pytest_sessionstart(session) -> None:
    """Refuse une collecte qui aurait déjà chargé le matériel réel."""
    imported = sorted(
        name
        for name in sys.modules
        if name in FORBIDDEN_HARDWARE_MODULES
        or any(name.startswith(f"{prefix}.") for prefix in FORBIDDEN_HARDWARE_MODULES)
    )
    if imported:
        raise RuntimeError(
            "Collecte interdite : modules matériel chargés avant les tests: "
            + ", ".join(imported)
        )
