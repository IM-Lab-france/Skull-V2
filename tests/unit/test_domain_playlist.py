from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.errors import ConflictError, DependencyUnavailableError, InvalidInputError
from domain.playlist import PlaybackStateStore, PlaylistStore, RandomSessionSelector


def test_playlist_store_preserves_legacy_queue_operations() -> None:
    playlist = PlaylistStore(clock=lambda: 123.0)

    first, first_position = playlist.add("Demo")
    second, second_position = playlist.add("Autre")

    assert first == {"id": 1, "session": "Demo", "added_at": 123.0, "retries": 0}
    assert second_position == 2
    assert first_position == 1
    assert playlist.move(second["id"], -1) == "moved"
    assert [item["session"] for item in playlist.snapshot()] == ["Autre", "Demo"]
    assert playlist.remove(first["id"])["session"] == "Demo"
    assert playlist.pop_next()["session"] == "Autre"
    assert playlist.pop_next() is None


def test_random_selector_is_injectably_deterministic() -> None:
    calls: list[str] = []

    def choose(values: list[str]) -> str:
        calls.append("choose")
        return values[-1]

    def shuffle(values: list[str]) -> None:
        calls.append("shuffle")
        values.reverse()

    selector = RandomSessionSelector(choice=choose, shuffle=shuffle)

    assert selector.eligible(["Accueil", "Demo", "Autre"], ["accueil"]) == (
        "Demo",
        "Autre",
    )
    assert selector.choose(["Demo", "Autre"]) == "Autre"
    values = ["Demo", "Autre"]
    selector.shuffle(values)
    assert values == ["Autre", "Demo"]
    assert calls == ["choose", "shuffle"]


def test_playback_state_store_returns_copies() -> None:
    state = PlaybackStateStore()
    state.set_current({"session": "Demo", "id": 1})

    current = state.get_current()
    current["session"] = "Changed"

    assert state.get_current() == {"session": "Demo", "id": 1}
    state.set_current(None)
    assert state.get_current() is None


def test_playlist_store_rejects_duplicate_item_ids() -> None:
    playlist = PlaylistStore(clock=lambda: 123.0)
    item, _ = playlist.add("Demo")

    with pytest.raises(ConflictError, match="Identifiants de playlist dupliqués"):
        playlist.push_front(item)

    assert [queued["session"] for queued in playlist.snapshot()] == ["Demo"]


def test_playlist_persistence_is_atomic_and_keeps_previous_file_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "playlist.json"
    playlist = PlaylistStore(path, clock=lambda: 123.0)
    playlist.add("Stable")
    previous = path.read_bytes()

    def fail_replace(source: str, target: str) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("domain.playlist.os.replace", fail_replace)
    with pytest.raises(DependencyUnavailableError):
        playlist.add("MustNotPersist")

    assert path.read_bytes() == previous
    assert [item["session"] for item in playlist.snapshot()] == ["Stable"]


def test_corrupt_playlist_is_rejected_without_repair(tmp_path: Path) -> None:
    path = tmp_path / "playlist.json"
    path.write_text("{not-json", encoding="utf-8")
    previous = path.read_bytes()

    with pytest.raises(InvalidInputError, match="Playlist invalide"):
        PlaylistStore(path)

    assert path.read_bytes() == previous


def test_playlist_file_has_a_stable_json_shape(tmp_path: Path) -> None:
    path = tmp_path / "playlist.json"
    playlist = PlaylistStore(path, clock=lambda: 123.0)
    playlist.add("Demo")

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "queue": [
            {"id": 1, "session": "Demo", "added_at": 123.0, "retries": 0}
        ]
    }
