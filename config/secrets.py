"""Narrow secret-reference resolver without logging or serializing values."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from .schema import ConfigurationError


_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def resolve_secret(reference: str, *, environ: Mapping[str, str] | None = None) -> str:
    """Resolve ``env:NAME`` or ``file:/absolute/path`` without exposing it."""
    if not isinstance(reference, str) or "\n" in reference or "\r" in reference:
        raise ConfigurationError("Secret indisponible: référence invalide")
    if reference.startswith("env:"):
        name = reference[4:]
        if not _ENV_NAME.fullmatch(name):
            raise ConfigurationError("Secret indisponible: référence env invalide")
        values = os.environ if environ is None else environ
        value = values.get(name)
        if not value:
            raise ConfigurationError("Secret indisponible: fournisseur env absent")
        return value
    if reference.startswith("file:"):
        filename = reference[5:]
        path = Path(filename)
        if not path.is_absolute() or not filename:
            raise ConfigurationError("Secret indisponible: fichier de secrets invalide")
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise ConfigurationError("Secret indisponible: fichier illisible") from exc
        if not value:
            raise ConfigurationError("Secret indisponible: valeur vide")
        return value
    raise ConfigurationError("Secret indisponible: référence env: ou file: attendue")


__all__ = ["resolve_secret"]
