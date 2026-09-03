"""Pure playlist and playback-state services for the Skull application."""

from __future__ import annotations

import json
import os
import random
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from .errors import ConflictError, DependencyUnavailableError, InvalidInputError
from .models import PlaylistItem


def _as_item(value: Mapping[str, Any]) -> PlaylistItem:
    try:
        item = PlaylistItem(
            id=int(value["id"]),
            session=str(value["session"]),
            added_at=float(value["added_at"]),
            retries=int(value.get("retries", 0)),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise InvalidInputError("Element de playlist invalide") from exc
    if item.id < 1 or item.retries < 0:
        raise InvalidInputError("Element de playlist invalide")
    return item


class PlaylistStore:
    """Thread-safe queue with an optional crash-safe JSON persistence file."""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._storage_path = Path(storage_path) if storage_path is not None else None
        self._queue: list[PlaylistItem] = self._load_from_disk()
        self._next_id = max((item.id for item in self._queue), default=0) + 1

    def add(self, session: str) -> tuple[dict[str, Any], int]:
        with self._lock:
            item = PlaylistItem(
                id=self._next_id,
                session=session,
                added_at=self._clock(),
                retries=0,
            )
            self._commit(self._queue + [item])
            self._next_id += 1
            return item.as_legacy_dict(), len(self._queue)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [item.as_legacy_dict() for item in self._queue]

    def pop_next(self) -> Optional[dict[str, Any]]:
        with self._lock:
            if not self._queue:
                return None
            item = self._queue[0]
            self._commit(self._queue[1:])
            return item.as_legacy_dict()

    def remove(self, item_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            for index, item in enumerate(self._queue):
                if item.id == item_id:
                    self._commit(self._queue[:index] + self._queue[index + 1 :])
                    return item.as_legacy_dict()
        return None

    def purge_session(self, session: str) -> list[dict[str, Any]]:
        with self._lock:
            removed = [item for item in self._queue if item.session == session]
            if not removed:
                return []
            kept = [item for item in self._queue if item.session != session]
            self._commit(kept)
            return [item.as_legacy_dict() for item in removed]

    def move(self, item_id: int, offset: int) -> str:
        with self._lock:
            for index, item in enumerate(self._queue):
                if item.id != item_id:
                    continue
                new_index = max(0, min(len(self._queue) - 1, index + offset))
                if new_index == index:
                    return "noop"
                updated = list(self._queue)
                updated.pop(index)
                updated.insert(new_index, item)
                self._commit(updated)
                return "moved"
        return "not_found"

    def push_front(self, item: Mapping[str, Any]) -> None:
        queued_item = _as_item(item)
        with self._lock:
            self._commit([queued_item] + self._queue)
            self._next_id = max(self._next_id, queued_item.id + 1)

    def clear(self) -> None:
        with self._lock:
            self._commit([])

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def has_items(self) -> bool:
        with self._lock:
            return bool(self._queue)

    def save(self) -> None:
        """Persist the current queue, if persistence was explicitly enabled."""
        with self._lock:
            self._persist(self._queue)

    def _commit(self, queue: list[PlaylistItem]) -> None:
        ids = [item.id for item in queue]
        if len(ids) != len(set(ids)):
            raise ConflictError("Identifiants de playlist dupliqués")
        self._persist(queue)
        self._queue = queue

    def _persist(self, queue: list[PlaylistItem]) -> None:
        if self._storage_path is None:
            return
        path = self._storage_path
        temporary_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {"queue": [item.as_legacy_dict() for item in queue]},
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        except OSError as exc:
            raise DependencyUnavailableError(
                "Persistance de playlist indisponible"
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _load_from_disk(self) -> list[PlaylistItem]:
        if self._storage_path is None or not self._storage_path.exists():
            return []
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise DependencyUnavailableError(
                "Lecture de playlist indisponible"
            ) from exc
        except json.JSONDecodeError as exc:
            raise InvalidInputError("Playlist invalide") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("queue"), list):
            raise InvalidInputError("Playlist invalide")
        try:
            items = [_as_item(value) for value in payload["queue"]]
        except InvalidInputError:
            raise InvalidInputError("Playlist invalide") from None
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ConflictError("Identifiants de playlist dupliqués")
        return items


class RandomSessionSelector:
    """Random session selection with injectable choice and shuffle functions."""

    def __init__(
        self,
        *,
        choice: Callable[[list[str]], str] = random.choice,
        shuffle: Callable[[list[str]], None] = random.shuffle,
    ) -> None:
        self._choice = choice
        self._shuffle = shuffle

    def eligible(
        self, names: Iterable[str], excluded: Iterable[str] = ()
    ) -> tuple[str, ...]:
        excluded_keys = {name.strip().lower() for name in excluded if name}
        return tuple(
            name
            for name in names
            if name.strip().lower() not in excluded_keys
        )

    def choose(self, names: Iterable[str]) -> str:
        return self._choice(list(names))

    def shuffle(self, names: list[str]) -> None:
        self._shuffle(names)


class PlaybackStateStore:
    """Thread-safe holder for the current legacy playback entry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: dict[str, Any] | None = None

    def set_current(self, entry: Mapping[str, Any] | None) -> None:
        with self._lock:
            self._current = dict(entry) if entry is not None else None

    def get_current(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._current) if self._current is not None else None


__all__ = ["PlaybackStateStore", "PlaylistStore", "RandomSessionSelector"]
