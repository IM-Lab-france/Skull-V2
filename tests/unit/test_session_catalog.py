from __future__ import annotations

from pathlib import Path

import pytest

from domain.errors import InvalidInputError
from domain.session_catalog import SessionCatalog


def write_session(root: Path, name: str, *, json_text: str = "{}", mp3: bool = True) -> Path:
    session = root / name
    session.mkdir()
    (session / "scene.json").write_text(json_text, encoding="utf-8")
    if mp3:
        (session / "scene.mp3").write_bytes(b"synthetic")
    return session


def test_catalog_lists_all_directories_in_stable_order(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    write_session(root, "zeta")
    (root / "Incomplet").mkdir()
    write_session(root, "Alpha")

    catalog = SessionCatalog(root)

    assert catalog.list_names() == ("Alpha", "Incomplet", "zeta")


def test_catalog_selects_duplicate_files_deterministically_without_repairing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    session = write_session(root, "Demo")
    (session / "alternate.json").write_text("{}", encoding="utf-8")
    (session / "alternate.mp3").write_bytes(b"synthetic")

    inspection = SessionCatalog(root).inspect("Demo")

    assert inspection.valid is True
    assert inspection.json_files == (
        session / "alternate.json",
        session / "scene.json",
    )
    assert inspection.mp3_files == (
        session / "alternate.mp3",
        session / "scene.mp3",
    )
    assert inspection.selected_json == session / "alternate.json"
    assert inspection.selected_mp3 == session / "alternate.mp3"
    assert inspection.issues == ()
    assert (session / "scene.json").exists()
    assert (session / "scene.mp3").exists()


@pytest.mark.parametrize(
    ("name", "json_text", "mp3", "message"),
    [
        ("MissingMp3", "{}", False, "Fichier MP3 introuvable dans la session"),
        ("InvalidJson", "{", True, "Fichier JSON invalide dans la session"),
        ("PartialJson", "", True, "Fichier JSON invalide dans la session"),
    ],
)
def test_catalog_reports_invalid_or_partial_sessions_deterministically(
    tmp_path: Path,
    name: str,
    json_text: str,
    mp3: bool,
    message: str,
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    write_session(root, name, json_text=json_text, mp3=mp3)

    inspection = SessionCatalog(root).inspect(name)

    assert inspection.valid is False
    assert inspection.issues
    with pytest.raises(InvalidInputError, match=message):
        SessionCatalog(root).require_playable(name)


def test_catalog_rejects_invalid_names_without_escaping_root(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    catalog = SessionCatalog(root)

    with pytest.raises(InvalidInputError, match="Nom de session invalide"):
        catalog.inspect("../outside")
