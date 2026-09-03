"""Legacy import façade for the pure timeline domain module."""

from domain.timeline import (
    CENTER_DEG,
    FPS,
    JAW_MAX,
    JAW_MIN,
    Timeline,
    _interp,
    _normalize_from_frames,
    _normalize_from_keyframes_root,
    _normalize_from_timeline,
    _normalize_from_top_level_channels,
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
