from __future__ import annotations

import json
from pathlib import Path

import pytest

from timeline import Timeline


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> Timeline:
    return Timeline.from_json(FIXTURES / name)


def test_all_reference_roots_and_basic_shapes() -> None:
    expected = {
        "timeline_root.json": (3, 1.0),
        "keyframes_root.json": (4, 0.05),
        "frames_root.json": (3, 0.1),
        "top_level_channels.json": (4, 0.05),
    }
    for filename, (frame_count, duration) in expected.items():
        timeline = load(filename)
        assert len(timeline.frames) == frame_count
        assert timeline.duration == pytest.approx(duration)
        assert all(set(frame) == {
            "timestamp_ms", "jaw_deg", "neck_pan_deg", "eye_left_deg", "eye_right_deg"
        } for frame in timeline.frames)


def test_timeline_root_uses_inverted_jaw_percentage() -> None:
    frames = load("timeline_root.json").frames
    assert [frame["timestamp_ms"] for frame in frames] == [0, 500, 1000]
    assert [frame["jaw_deg"] for frame in frames] == pytest.approx([185.0, 92.5, 0.0])
    assert frames[0]["neck_pan_deg"] == pytest.approx(80.0)


def test_keyframes_and_frames_use_ascending_jaw_percentage() -> None:
    keyframes = load("keyframes_root.json").frames
    frames = load("frames_root.json").frames
    assert keyframes[0]["jaw_deg"] == pytest.approx(0.0)
    assert keyframes[-1]["jaw_deg"] == pytest.approx(185.0)
    assert [frame["jaw_deg"] for frame in frames] == pytest.approx([0.0, 92.5, 185.0])


def test_missing_channels_use_current_reference_defaults() -> None:
    frame = load("timeline_missing_channel.json").frames[0]
    assert frame["jaw_deg"] == pytest.approx(92.5)
    assert frame["neck_pan_deg"] == pytest.approx(90.0)
    assert frame["eye_left_deg"] == pytest.approx(90.0)
    assert frame["eye_right_deg"] == pytest.approx(90.0)


def test_duplicate_keyframe_time_keeps_reference_ordering() -> None:
    frames = load("timeline_duplicate_keyframe.json").frames
    assert frames[0]["jaw_deg"] == pytest.approx(18.5)
    assert frames[1]["jaw_deg"] == pytest.approx(37.3, abs=0.1)


def test_boundary_and_out_of_range_values_are_not_clamped() -> None:
    boundary = load("timeline_boundary.json").frames
    assert boundary[0]["jaw_deg"] == pytest.approx(37.0)
    assert boundary[-1]["jaw_deg"] == pytest.approx(55.5)

    out = load("timeline_out_of_range.json").frames
    assert out[0]["neck_pan_deg"] == pytest.approx(290.0)
    assert out[0]["eye_left_deg"] == pytest.approx(-110.0)
    assert out[0]["jaw_deg"] == pytest.approx(203.5)


def test_zero_duration_still_emits_one_frame() -> None:
    timeline = load("timeline_zero_duration.json")
    assert timeline.duration == pytest.approx(0.0)
    assert len(timeline.frames) == 2
    assert [frame["timestamp_ms"] for frame in timeline.frames] == [0, 16]


@pytest.mark.parametrize(
    ("filename", "error"),
    [
        ("empty.json", json.JSONDecodeError),
        ("invalid.json", json.JSONDecodeError),
        ("unknown.json", ValueError),
    ],
)
def test_invalid_and_unknown_formats_are_rejected(filename: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        load(filename)
