"""Filesystem catalogue for playable Skull sessions.

The catalogue owns discovery and validation only.  It never deletes, rewrites,
or repairs a session.  Flask and the hardware player can consume its result
without importing this module's runtime dependencies because it uses only the
Python standard library and the domain error types.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import DependencyUnavailableError, InvalidInputError, NotFoundError


def _stable_path_key(path: Path) -> tuple[str, str]:
    """Match the legacy case-insensitive order and make ties deterministic."""
    return path.name.lower(), path.name


@dataclass(frozen=True, slots=True)
class SessionInspection:
    """A deterministic, side-effect-free inspection of one session folder."""

    name: str
    path: Path
    json_files: tuple[Path, ...]
    mp3_files: tuple[Path, ...]
    selected_json: Path | None
    selected_mp3: Path | None
    issues: tuple[str, ...]
    valid: bool


class SessionCatalog:
    """Discover and validate direct child session folders under a root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def list_names(self) -> tuple[str, ...]:
        """Return every direct directory, including incomplete sessions.

        The legacy `/sessions` route exposes directory names before checking
        playable files.  Keeping incomplete names here preserves that visible
        behaviour while `inspect` and `require_playable` expose their status.
        """
        try:
            entries = [entry for entry in self.root.iterdir() if entry.is_dir()]
        except FileNotFoundError:
            return ()
        except OSError as exc:
            raise DependencyUnavailableError(
                "Catalogue de sessions indisponible"
            ) from exc
        return tuple(entry.name for entry in sorted(entries, key=_stable_path_key))

    def resolve(self, name: str) -> Path:
        """Resolve one direct child directory without inspecting its contents."""
        self._validate_name(name)
        candidate = (self.root / name).resolve(strict=False)
        if not candidate.exists() or not candidate.is_dir():
            raise NotFoundError(name)
        return candidate

    def inspect(self, name: str) -> SessionInspection:
        """Inspect files and JSON validity without changing the filesystem."""
        session_dir = self.resolve(name)
        json_files = tuple(
            sorted(
                (path for path in session_dir.glob("*.json") if path.is_file()),
                key=_stable_path_key,
            )
        )
        mp3_files = tuple(
            sorted(
                (path for path in session_dir.glob("*.mp3") if path.is_file()),
                key=_stable_path_key,
            )
        )

        selected_json = json_files[0] if json_files else None
        selected_mp3 = mp3_files[0] if mp3_files else None
        issues: list[str] = []
        if selected_json is None:
            issues.append("missing_json")
        else:
            try:
                json.loads(selected_json.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                issues.append("unreadable_json")
            except json.JSONDecodeError:
                issues.append("invalid_json")

        if selected_mp3 is None:
            issues.append("missing_mp3")
        else:
            try:
                if selected_mp3.stat().st_size == 0:
                    issues.append("partial_mp3")
            except OSError:
                issues.append("unreadable_mp3")

        return SessionInspection(
            name=name,
            path=session_dir,
            json_files=json_files,
            mp3_files=mp3_files,
            selected_json=selected_json,
            selected_mp3=selected_mp3,
            issues=tuple(issues),
            valid=not issues,
        )

    def require_playable(self, name: str) -> Path:
        """Return a playable folder or a stable legacy-compatible error."""
        inspection = self.inspect(name)
        if inspection.valid:
            return inspection.path

        if "missing_json" in inspection.issues:
            raise InvalidInputError("Fichier JSON introuvable dans la session")
        if "missing_mp3" in inspection.issues:
            raise InvalidInputError("Fichier MP3 introuvable dans la session")
        if "invalid_json" in inspection.issues:
            raise InvalidInputError("Fichier JSON invalide dans la session")
        if "unreadable_json" in inspection.issues:
            raise InvalidInputError("Fichier JSON indisponible dans la session")
        if "partial_mp3" in inspection.issues:
            raise InvalidInputError("Fichier MP3 partiellement écrit dans la session")
        raise InvalidInputError("Fichiers de session indisponibles")

    def _validate_name(self, name: str) -> None:
        if not isinstance(name, str) or not name or name in {".", ".."}:
            raise InvalidInputError("Nom de session invalide")
        if "/" in name or "\\" in name or "\x00" in name:
            raise InvalidInputError("Nom de session invalide")
        try:
            candidate = (self.root / name).resolve(strict=False)
        except (OSError, RuntimeError, ValueError) as exc:
            raise InvalidInputError("Nom de session invalide") from exc
        if candidate.parent != self.root:
            raise InvalidInputError("Nom de session invalide")


__all__ = ["SessionCatalog", "SessionInspection"]
