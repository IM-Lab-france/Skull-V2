from __future__ import annotations

import subprocess
import sys

import pytest

from domain.errors import (
    ConflictError,
    DependencyUnavailableError,
    DomainError,
    InvalidInputError,
    NotFoundError,
    OperationNotAllowedError,
)
from domain.models import (
    PlaybackSnapshot,
    PlaybackState,
    PlaylistItem,
    Session,
    TimelineEvent,
)


def test_domain_types_are_importable_without_runtime_dependencies() -> None:
    code = (
        "import sys; import domain; "
        "forbidden = {'flask', 'requests', 'subprocess', 'RPi', 'board', 'busio'}; "
        "assert not forbidden.intersection(sys.modules); "
        "print(domain.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "domain"


def test_domain_models_capture_current_skull_shapes() -> None:
    session = Session(name="Accueil", category="general")
    event = TimelineEvent(
        timestamp_ms=100,
        jaw_deg=120.0,
        neck_pan_deg=90.0,
        eye_left_deg=90.0,
        eye_right_deg=90.0,
    )
    item = PlaylistItem(id=1, session=session.name, added_at=123.0, retries=0)
    snapshot = PlaybackSnapshot(
        state=PlaybackState.PLAYING,
        session=session.name,
        elapsed_ms=100,
        channels={"jaw": True},
    )

    assert session.name == "Accueil"
    assert event.as_legacy_dict()["timestamp_ms"] == 100
    assert item.as_legacy_dict()["session"] == "Accueil"
    assert snapshot.as_legacy_dict()["running"] is True
    assert snapshot.as_legacy_dict()["paused"] is False


def test_domain_models_are_immutable() -> None:
    session = Session(name="Accueil")
    with pytest.raises(AttributeError):
        session.name = "Autre"  # type: ignore[misc]


def test_domain_errors_keep_legacy_exception_compatibility() -> None:
    assert issubclass(NotFoundError, (DomainError, FileNotFoundError))
    assert issubclass(InvalidInputError, (DomainError, ValueError))
    assert issubclass(ConflictError, DomainError)
    assert issubclass(DependencyUnavailableError, (DomainError, ConnectionError))
    assert issubclass(OperationNotAllowedError, (DomainError, PermissionError))
