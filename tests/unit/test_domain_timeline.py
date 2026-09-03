from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.errors import InvalidInputError
from domain.timeline import Timeline


FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.parametrize(
    ("filename", "frame_count", "duration"),
    [
        ("timeline_root.json", 3, 1.0),
        ("keyframes_root.json", 4, 0.05),
        ("frames_root.json", 3, 0.1),
        ("top_level_channels.json", 4, 0.05),
    ],
)
def test_domain_timeline_preserves_reference_formats(
    filename: str, frame_count: int, duration: float
) -> None:
    timeline = Timeline.from_json(FIXTURES / filename)

    assert len(timeline.frames) == frame_count
    assert timeline.duration == pytest.approx(duration)
    assert all(
        set(frame)
        == {
            "timestamp_ms",
            "jaw_deg",
            "neck_pan_deg",
            "eye_left_deg",
            "eye_right_deg",
        }
        for frame in timeline.frames
    )


def test_domain_timeline_keeps_simultaneous_events_and_empty_timeline(
    tmp_path: Path,
) -> None:
    duplicate = Timeline.from_json(FIXTURES / "timeline_duplicate_keyframe.json")
    empty_path = tmp_path / "domain_empty_timeline.json"
    empty_path.write_text(json.dumps({"timeline": []}), encoding="utf-8")
    try:
        empty = Timeline.from_json(empty_path)
    finally:
        empty_path.unlink()

    assert duplicate.frames[0]["jaw_deg"] == pytest.approx(18.5)
    assert empty.frames == []
    assert empty.duration == 0.0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"frames": [{"timestamp_ms": 10}, {"timestamp_ms": 9}]},
            "Événement 1 invalide",
        ),
        (
            {
                "timeline": [
                    {"time": 0.0, "motors": {"unknownMotor": 1}}
                ]
            },
            "Événement 0 invalide",
        ),
        (
            {"frames": [{"timestamp_ms": "not-a-number"}]},
            "Événement 0 invalide",
        ),
    ],
)
def test_domain_timeline_reports_indexed_validation_errors(
    tmp_path: Path, payload: dict[str, object], message: str
) -> None:
    path = tmp_path / "invalid-timeline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(InvalidInputError, match=message):
        Timeline.from_json(path)


def test_domain_timeline_rejects_non_finite_values(tmp_path: Path) -> None:
    path = tmp_path / "non-finite-timeline.json"
    path.write_text(
        '{"timeline": [{"time": 0.0, "motors": {"jawOpening": NaN}}]}',
        encoding="utf-8",
    )

    with pytest.raises(InvalidInputError, match="Événement 0 invalide"):
        Timeline.from_json(path)
