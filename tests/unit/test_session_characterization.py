from __future__ import annotations

import sys
import types
import os
from pathlib import Path

import pytest


def load_session_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Charge web_app avec des adaptateurs matériels factices uniquement."""
    class FakePlayer:
        def __init__(self) -> None:
            self.hw = types.SimpleNamespace(SPECS={})

        def set_on_track_finished(self, callback) -> None:
            self.callback = callback

    class FakeLoopPlayer:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def set_on_track_finished(self, callback) -> None:
            self.callback = callback

    class FakeLogger:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    fake_sync = types.ModuleType("sync_player")
    fake_sync.SyncPlayer = FakePlayer
    fake_loop = types.ModuleType("loop_player")
    fake_loop.LoopPlayer = FakeLoopPlayer
    fake_logger = types.ModuleType("logger")
    fake_logger.servo_logger = types.SimpleNamespace(logger=FakeLogger())

    for name, module in {
        "sync_player": fake_sync,
        "loop_player": fake_loop,
        "logger": fake_logger,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKULL_SMOKE_WEBHOOK_URL", "")
    sys.modules.pop("web_app", None)
    import web_app

    web_app.DATA_DIR = tmp_path / "data"
    web_app.DATA_DIR.mkdir(exist_ok=True)
    return web_app


def make_session(data_dir: Path, name: str, *, mp3=True, json_file=True, wav=False) -> Path:
    session = data_dir / name
    session.mkdir()
    if mp3:
        (session / "scene.mp3").write_bytes(b"synthetic placeholder")
    if json_file:
        (session / "scene.json").write_text("{}", encoding="utf-8")
    if wav:
        (session / "scene.cached.wav").write_bytes(b"synthetic cache")
    return session


def test_exactly_one_mp3_and_json_is_accepted(tmp_path, monkeypatch) -> None:
    api = load_session_api(tmp_path, monkeypatch)
    session = make_session(api.DATA_DIR, "Scene Été Skull")
    assert api._ensure_session_exists(session.name) == session.resolve()


def test_wav_cache_is_ignored_and_multiple_files_are_accepted(tmp_path, monkeypatch) -> None:
    api = load_session_api(tmp_path, monkeypatch)
    session = make_session(api.DATA_DIR, "Avec espaces", wav=True)
    (session / "alternate.mp3").write_bytes(b"synthetic")
    (session / "alternate.json").write_text("{}", encoding="utf-8")
    assert api._ensure_session_exists(session.name) == session.resolve()
    assert sorted(p.name for p in session.glob("*.mp3")) == ["alternate.mp3", "scene.mp3"]


@pytest.mark.parametrize(
    ("mp3", "json_file", "message"),
    [
        (False, True, "Fichier MP3 introuvable dans la session"),
        (True, False, "Fichier JSON introuvable dans la session"),
        (False, False, "Fichier JSON introuvable dans la session"),
    ],
)
def test_missing_required_files_are_rejected(tmp_path, monkeypatch, mp3, json_file, message) -> None:
    api = load_session_api(tmp_path, monkeypatch)
    session = make_session(api.DATA_DIR, "Vide", mp3=mp3, json_file=json_file)
    with pytest.raises(ValueError, match=message):
        api._ensure_session_exists(session.name)


def test_empty_session_is_reported_as_missing_json(tmp_path, monkeypatch) -> None:
    api = load_session_api(tmp_path, monkeypatch)
    (api.DATA_DIR / "Empty").mkdir()
    with pytest.raises(ValueError, match="Fichier JSON introuvable"):
        api._ensure_session_exists("Empty")


def test_unknown_and_traversal_names_are_rejected(tmp_path, monkeypatch) -> None:
    api = load_session_api(tmp_path, monkeypatch)
    make_session(api.DATA_DIR, "Accueil")
    with pytest.raises(ValueError, match="Session introuvable"):
        api._ensure_session_exists("DoesNotExist")
    with pytest.raises(ValueError, match="Nom de session invalide"):
        api._ensure_session_exists("../Accueil")
    with pytest.raises(ValueError, match="Nom de session invalide"):
        api._ensure_session_exists(str(api.DATA_DIR / "Accueil" / ".."))


def test_directory_name_is_case_sensitive_but_unicode_and_spaces_work(tmp_path, monkeypatch) -> None:
    api = load_session_api(tmp_path, monkeypatch)
    session = make_session(api.DATA_DIR, "Scène Adulte")
    assert api._ensure_session_exists("Scène Adulte") == session.resolve()
    if os.name == "nt":
        assert api._ensure_session_exists("scène adulte") == session.resolve()
    else:
        with pytest.raises(ValueError, match="Session introuvable"):
            api._ensure_session_exists("scène adulte")
