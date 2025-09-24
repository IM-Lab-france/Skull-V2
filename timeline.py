from __future__ import annotations

import json
import bisect
from pathlib import Path
from typing import Dict, List, Iterator, Any

FPS = 60  # interpolation rate

# Servo mapping assumptions
CENTER_DEG = 90.0
JAW_MIN = 0.0  # must match rpi_hardware.Hardware.SPECS["jaw"].min_deg
JAW_MAX = 185.0  # must match rpi_hardware.Hardware.SPECS["jaw"].max_deg


def _interp(keyframes: List[Dict[str, float]], t: float) -> float:
    if not keyframes:
        return CENTER_DEG
    times = [float(k["time"]) for k in keyframes]
    angles = [float(k["angle"]) for k in keyframes]
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
    """
    Accepts: {"timeline":[
        {"time": 0.0, "motors": {
            "neckYaw": +/-deg, "eyeLeftYaw": +/-deg, "eyeRightYaw": +/-deg,
            "jawOpening": 0..100
        }}, ...
    ], "metadata":{...}}
    """
    tl = data["timeline"]
    frames: list[dict] = []
    last_t = 0.0
    for f in tl:
        t = float(f.get("time", 0.0))
        last_t = max(last_t, t)
        m = f.get("motors", {})
        neck = float(m.get("neckYaw", 0.0))
        eye_l = float(m.get("eyeLeftYaw", 0.0))
        eye_r = float(m.get("eyeRightYaw", 0.0))
        jaw_pct = float(m.get("jawOpening", 0.0))  # 0..100

        # Map to absolute servo angles
        jaw_deg = JAW_MAX - (jaw_pct / 100.0) * (JAW_MAX - JAW_MIN)
        frames.append(
            {
                "timestamp_ms": int(t * 1000),
                "jaw_deg": jaw_deg,
                "neck_pan_deg": CENTER_DEG + neck,
                "eye_left_deg": CENTER_DEG + eye_l,
                "eye_right_deg": CENTER_DEG + eye_r,
            }
        )
    duration = last_t
    return frames, duration


def _normalize_from_keyframes_root(data: Dict[str, Any]) -> tuple[list[dict], float]:
    meta = data.get("metadata", {})
    duration = float(meta.get("duration", 0.0))
    kf = data["keyframes"]
    channels = {
        "jaw": kf.get("jaw_deg") or kf.get("jawOpening") or [],
        "neck": kf.get("neckYaw") or [],
        "eye_l": kf.get("eyeLeftYaw") or [],
        "eye_r": kf.get("eyeRightYaw") or [],
    }
    if duration <= 0.0:
        max_t = 0.0
        for arr in channels.values():
            if arr:
                max_t = max(max_t, float(arr[-1]["time"]))
        duration = max_t
    nframes = max(1, int(duration * FPS))
    out: list[dict] = []
    for i in range(nframes + 1):
        t = i / FPS
        jaw = _interp(channels["jaw"], t)
        # if jaw channel is percentage-like (0..100), map to angle:
        if 0.0 <= jaw <= 100.0:
            jaw = JAW_MIN + (jaw / 100.0) * (JAW_MAX - JAW_MIN)
        out.append(
            {
                "timestamp_ms": int(t * 1000),
                "jaw_deg": jaw,
                "neck_pan_deg": _interp(channels["neck"], t) + CENTER_DEG,
                "eye_left_deg": _interp(channels["eye_l"], t) + CENTER_DEG,
                "eye_right_deg": _interp(channels["eye_r"], t) + CENTER_DEG,
            }
        )
    return out, duration


def _normalize_from_frames(data: Dict[str, Any]) -> tuple[list[dict], float]:
    frames_in = data["frames"]
    out: list[dict] = []
    last_ms = 0
    for f in frames_in:
        ts = int(f.get("timestamp_ms") or f.get("t_ms") or 0)
        last_ms = max(last_ms, ts)
        jaw = float(f.get("jaw_deg", f.get("jawOpening", 0.0)))
        if 0.0 <= jaw <= 100.0:
            jaw = JAW_MIN + (jaw / 100.0) * (JAW_MAX - JAW_MIN)
        neck = float(f.get("neck_pan_deg", f.get("neckYaw", 0.0))) + CENTER_DEG
        eye_l = float(f.get("eye_left_deg", f.get("eyeLeftYaw", 0.0))) + CENTER_DEG
        eye_r = float(f.get("eye_right_deg", f.get("eyeRightYaw", 0.0))) + CENTER_DEG
        out.append(
            {
                "timestamp_ms": ts,
                "jaw_deg": jaw,
                "neck_pan_deg": neck,
                "eye_left_deg": eye_l,
                "eye_right_deg": eye_r,
            }
        )
    duration = last_ms / 1000.0
    return out, duration


def _normalize_from_top_level_channels(
    data: Dict[str, Any],
) -> tuple[list[dict], float]:
    channels = {
        "jaw": data.get("jaw_deg") or data.get("jawOpening") or [],
        "neck": data.get("neckYaw") or [],
        "eye_l": data.get("eyeLeftYaw") or [],
        "eye_r": data.get("eyeRightYaw") or [],
    }
    if not any(channels.values()):
        raise ValueError(
            "Aucune piste trouvée (attendues: jaw_deg|jawOpening, neckYaw, eyeLeftYaw, eyeRightYaw)."
        )
    duration = 0.0
    for arr in channels.values():
        if arr:
            duration = max(duration, float(arr[-1]["time"]))
    nframes = max(1, int(duration * FPS))
    out: list[dict] = []
    for i in range(nframes + 1):
        t = i / FPS
        jaw = _interp(channels["jaw"], t)
        if 0.0 <= jaw <= 100.0:
            jaw = JAW_MIN + (jaw / 100.0) * (JAW_MAX - JAW_MIN)
        out.append(
            {
                "timestamp_ms": int(t * 1000),
                "jaw_deg": jaw,
                "neck_pan_deg": _interp(channels["neck"], t) + CENTER_DEG,
                "eye_left_deg": _interp(channels["eye_l"], t) + CENTER_DEG,
                "eye_right_deg": _interp(channels["eye_r"], t) + CENTER_DEG,
            }
        )
    return out, duration


class Timeline:
    def __init__(self, frames: List[Dict[str, float]], duration: float):
        self.frames = frames
        self.duration = duration

    def __iter__(self) -> Iterator[Dict[str, float]]:
        return iter(self.frames)

    @classmethod
    def from_json(cls, path: str | Path) -> "Timeline":
        """
        Charge une timeline depuis un fichier JSON.
        Supporte le nouveau format de noms (SceneName_60Hz.json)
        """
        json_path = Path(path)

        # Si on passe juste un répertoire, chercher le fichier JSON
        if json_path.is_dir():
            json_files = list(json_path.glob("*.json"))
            if not json_files:
                raise FileNotFoundError(f"Aucun fichier JSON trouvé dans {json_path}")
            # Prendre le premier (ou on pourrait prioriser par fréquence)
            json_path = json_files[0]

        if not json_path.exists():
            raise FileNotFoundError(f"Fichier JSON introuvable: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))

        if isinstance(data, dict) and "timeline" in data:  # NEW
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

        raise ValueError(
            "Format JSON non reconnu: attendu 'timeline', 'keyframes', 'frames' ou canaux top-level."
        )
