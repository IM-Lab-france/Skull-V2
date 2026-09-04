"""Pure parsing, validation, normalization, and interpolation of timelines."""

from __future__ import annotations

import bisect
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterator, List

from .errors import InvalidInputError, NotFoundError
from .models import TimelineEvent


FPS = 60
CENTER_DEG = 90.0
JAW_MIN = 0.0
JAW_MAX = 185.0

_TIMELINE_CHANNELS = {"neckYaw", "eyeLeftYaw", "eyeRightYaw", "jawOpening"}
_KEYFRAME_CHANNELS = {
    "jaw_deg",
    "jawOpening",
    "neckYaw",
    "eyeLeftYaw",
    "eyeRightYaw",
}
_FRAME_FIELDS = {
    "timestamp_ms",
    "t_ms",
    "jaw_deg",
    "jawOpening",
    "neck_pan_deg",
    "neckYaw",
    "eye_left_deg",
    "eyeLeftYaw",
    "eye_right_deg",
    "eyeRightYaw",
}


def _invalid(index: int, detail: str) -> InvalidInputError:
    return InvalidInputError(f"Événement {index} invalide: {detail}")


def _finite_number(value: Any, index: int, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _invalid(index, f"{field} doit être numérique") from exc
    if not math.isfinite(number):
        raise _invalid(index, f"{field} doit être fini")
    return number


def _require_list(value: Any, index: int, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _invalid(index, f"{field} doit être une liste")
    return value


def _validate_known_channels(
    keys: set[str], allowed: set[str], *, index: int | None = None
) -> None:
    unknown = sorted(keys - allowed)
    if unknown:
        if index is None:
            raise InvalidInputError(f"Canal inconnu: {unknown[0]}")
        raise _invalid(index, f"canal inconnu: {unknown[0]}")


def _validate_keyframes(
    values: Any, channel: str, *, start_index: int = 0
) -> list[dict[str, float]]:
    points = _require_list(values, start_index, f"canal {channel}")
    normalized: list[dict[str, float]] = []
    previous_time: float | None = None
    for index, point in enumerate(points, start=start_index):
        if not isinstance(point, dict):
            raise _invalid(index, f"canal {channel} doit contenir des objets")
        timestamp = _finite_number(point.get("time"), index, f"{channel}.time")
        angle = _finite_number(point.get("angle"), index, f"{channel}.angle")
        if previous_time is not None and timestamp < previous_time:
            raise _invalid(index, f"{channel}.time doit être croissant")
        previous_time = timestamp
        normalized.append({"time": timestamp, "angle": angle})
    return normalized


def _interp(keyframes: List[Dict[str, float]], t: float) -> float:
    if not keyframes:
        return CENTER_DEG
    times = [k["time"] for k in keyframes]
    angles = [k["angle"] for k in keyframes]
    if t <= times[0]:
        return angles[0]
    if t >= times[-1]:
        return angles[-1]
    i = bisect.bisect_left(times, t)
    t0, t1 = times[i - 1], times[i]
    a0, a1 = angles[i - 1], angles[i]
    alpha = (t - t0) / (t1 - t0) if (t1 - t0) else 0.0
    return a0 + alpha * (a1 - a0)


def _normalize_from_timeline(data: Dict[str, Any]) -> tuple[list[dict], float]:
    timeline = data["timeline"]
    if not isinstance(timeline, list):
        raise _invalid(0, "timeline doit être une liste")
    frames: list[dict] = []
    last_time: float | None = None
    for index, frame in enumerate(timeline):
        if not isinstance(frame, dict):
            raise _invalid(index, "timeline doit contenir des objets")
        timestamp = _finite_number(frame.get("time", 0.0), index, "time")
        if last_time is not None and timestamp < last_time:
            raise _invalid(index, "time doit être croissant")
        last_time = timestamp
        motors = frame.get("motors", {})
        if not isinstance(motors, dict):
            raise _invalid(index, "motors doit être un objet")
        _validate_known_channels(set(motors), _TIMELINE_CHANNELS, index=index)
        neck = _finite_number(motors.get("neckYaw", 0.0), index, "neckYaw")
        eye_l = _finite_number(
            motors.get("eyeLeftYaw", 0.0), index, "eyeLeftYaw"
        )
        eye_r = _finite_number(
            motors.get("eyeRightYaw", 0.0), index, "eyeRightYaw"
        )
        jaw_pct = _finite_number(
            motors.get("jawOpening", 0.0), index, "jawOpening"
        )
        jaw_deg = JAW_MAX - (jaw_pct / 100.0) * (JAW_MAX - JAW_MIN)
        frames.append(
            {
                "timestamp_ms": int(timestamp * 1000),
                "jaw_deg": jaw_deg,
                "neck_pan_deg": CENTER_DEG + neck,
                "eye_left_deg": CENTER_DEG + eye_l,
                "eye_right_deg": CENTER_DEG + eye_r,
            }
        )
    return frames, max(0.0, last_time or 0.0)


def _channels_from_keyframes(data: Dict[str, Any]) -> dict[str, list[dict[str, float]]]:
    keyframes = data["keyframes"]
    if not isinstance(keyframes, dict):
        raise _invalid(0, "keyframes doit être un objet")
    _validate_known_channels(set(keyframes), _KEYFRAME_CHANNELS, index=0)
    jaw_values = keyframes.get("jaw_deg") or keyframes.get("jawOpening") or []
    return {
        "jaw": _validate_keyframes(jaw_values, "jaw", start_index=0),
        "neck": _validate_keyframes(keyframes.get("neckYaw"), "neck", start_index=0),
        "eye_l": _validate_keyframes(
            keyframes.get("eyeLeftYaw"), "eye_l", start_index=0
        ),
        "eye_r": _validate_keyframes(
            keyframes.get("eyeRightYaw"), "eye_r", start_index=0
        ),
    }


def _normalize_from_keyframes_root(data: Dict[str, Any]) -> tuple[list[dict], float]:
    meta = data.get("metadata", {})
    if not isinstance(meta, dict):
        raise _invalid(0, "metadata doit être un objet")
    duration = _finite_number(meta.get("duration", 0.0), 0, "duration")
    channels = _channels_from_keyframes(data)
    if duration <= 0.0:
        duration = 0.0
        for values in channels.values():
            if values:
                duration = max(duration, values[-1]["time"])

    nframes = max(1, int(duration * FPS))
    output: list[dict] = []
    for index in range(nframes + 1):
        timestamp = index / FPS
        jaw = _interp(channels["jaw"], timestamp)
        if 0.0 <= jaw <= 100.0:
            jaw = JAW_MIN + (jaw / 100.0) * (JAW_MAX - JAW_MIN)
        output.append(
            {
                "timestamp_ms": int(timestamp * 1000),
                "jaw_deg": jaw,
                "neck_pan_deg": _interp(channels["neck"], timestamp) + CENTER_DEG,
                "eye_left_deg": _interp(channels["eye_l"], timestamp) + CENTER_DEG,
                "eye_right_deg": _interp(channels["eye_r"], timestamp) + CENTER_DEG,
            }
        )
    return output, duration


def _normalize_from_frames(data: Dict[str, Any]) -> tuple[list[dict], float]:
    frames_in = data["frames"]
    if not isinstance(frames_in, list):
        raise _invalid(0, "frames doit être une liste")
    output: list[dict] = []
    previous_timestamp: int | None = None
    last_ms = 0
    for index, frame in enumerate(frames_in):
        if not isinstance(frame, dict):
            raise _invalid(index, "frames doit contenir des objets")
        _validate_known_channels(set(frame) & _FRAME_FIELDS, _FRAME_FIELDS)
        raw_timestamp = frame.get("timestamp_ms") or frame.get("t_ms") or 0
        timestamp = int(_finite_number(raw_timestamp, index, "timestamp_ms"))
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise _invalid(index, "timestamp_ms doit être croissant")
        previous_timestamp = timestamp
        last_ms = max(last_ms, timestamp)
        jaw_value = frame.get("jaw_deg", frame.get("jawOpening", 0.0))
        jaw = _finite_number(jaw_value, index, "jaw_deg")
        if 0.0 <= jaw <= 100.0:
            jaw = JAW_MIN + (jaw / 100.0) * (JAW_MAX - JAW_MIN)
        neck = _finite_number(
            frame.get("neck_pan_deg", frame.get("neckYaw", 0.0)), index, "neck"
        ) + CENTER_DEG
        eye_l = _finite_number(
            frame.get("eye_left_deg", frame.get("eyeLeftYaw", 0.0)), index, "eye_left"
        ) + CENTER_DEG
        eye_r = _finite_number(
            frame.get("eye_right_deg", frame.get("eyeRightYaw", 0.0)), index, "eye_right"
        ) + CENTER_DEG
        output.append(
            {
                "timestamp_ms": timestamp,
                "jaw_deg": jaw,
                "neck_pan_deg": neck,
                "eye_left_deg": eye_l,
                "eye_right_deg": eye_r,
            }
        )
    return output, last_ms / 1000.0


def _normalize_from_top_level_channels(data: Dict[str, Any]) -> tuple[list[dict], float]:
    allowed = _KEYFRAME_CHANNELS | {"metadata"}
    _validate_known_channels(set(data), allowed, index=0)
    channels = {
        "jaw": _validate_keyframes(
            data.get("jaw_deg") or data.get("jawOpening") or [], "jaw"
        ),
        "neck": _validate_keyframes(data.get("neckYaw"), "neck"),
        "eye_l": _validate_keyframes(data.get("eyeLeftYaw"), "eye_l"),
        "eye_r": _validate_keyframes(data.get("eyeRightYaw"), "eye_r"),
    }
    if not any(channels.values()):
        raise InvalidInputError(
            "Aucune piste trouvée (attendues: jaw_deg|jawOpening, neckYaw, eyeLeftYaw, eyeRightYaw)."
        )
    duration = 0.0
    for values in channels.values():
        if values:
            duration = max(duration, values[-1]["time"])
    nframes = max(1, int(duration * FPS))
    output: list[dict] = []
    for index in range(nframes + 1):
        timestamp = index / FPS
        jaw = _interp(channels["jaw"], timestamp)
        if 0.0 <= jaw <= 100.0:
            jaw = JAW_MIN + (jaw / 100.0) * (JAW_MAX - JAW_MIN)
        output.append(
            {
                "timestamp_ms": int(timestamp * 1000),
                "jaw_deg": jaw,
                "neck_pan_deg": _interp(channels["neck"], timestamp) + CENTER_DEG,
                "eye_left_deg": _interp(channels["eye_l"], timestamp) + CENTER_DEG,
                "eye_right_deg": _interp(channels["eye_r"], timestamp) + CENTER_DEG,
            }
        )
    return output, duration


class Timeline:
    """Normalized timeline retaining the legacy dictionary frame interface."""

    def __init__(self, frames: List[Dict[str, float]], duration: float):
        self.frames = frames
        self.duration = duration

    def __iter__(self) -> Iterator[Dict[str, float]]:
        return iter(self.frames)

    @property
    def events(self) -> tuple[TimelineEvent, ...]:
        """Typed view of the normalized frames for new domain callers."""
        return tuple(TimelineEvent(**frame) for frame in self.frames)

    @classmethod
    def from_json(cls, path: str | Path) -> "Timeline":
        json_path = Path(path)
        if json_path.is_dir():
            json_files = sorted(json_path.glob("*.json"), key=lambda item: item.name.lower())
            if not json_files:
                raise NotFoundError(f"Aucun fichier JSON trouvé dans {json_path}")
            json_path = json_files[0]
        if not json_path.exists():
            raise NotFoundError(f"Fichier JSON introuvable: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "timeline" in data:
            frames, duration = _normalize_from_timeline(data)
            return cls(frames, duration)
        if isinstance(data, dict) and "keyframes" in data:
            frames, duration = _normalize_from_keyframes_root(data)
            return cls(frames, duration)
        if isinstance(data, dict) and "frames" in data:
            frames, duration = _normalize_from_frames(data)
            return cls(frames, duration)
        if isinstance(data, dict):
            frames, duration = _normalize_from_top_level_channels(data)
            return cls(frames, duration)
        raise InvalidInputError(
            "Format JSON non reconnu: attendu 'timeline', 'keyframes', 'frames' ou canaux top-level."
        )


__all__ = [
    "CENTER_DEG",
    "FPS",
    "JAW_MAX",
    "JAW_MIN",
    "Timeline",
    "_interp",
    "_normalize_from_frames",
    "_normalize_from_keyframes_root",
    "_normalize_from_timeline",
    "_normalize_from_top_level_channels",
]
