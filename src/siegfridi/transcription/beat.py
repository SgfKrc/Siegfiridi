"""Beat and tempo estimation with a librosa adapter and deterministic fallback."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BeatEstimate:
    bpm: float
    beat_times: tuple[float, ...]
    confidence: float
    source: str

    def __post_init__(self) -> None:
        if self.bpm <= 0:
            raise ValueError("bpm must be positive")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


def _fallback_beats(duration_seconds: float, bpm: float) -> BeatEstimate:
    if duration_seconds <= 0:
        return BeatEstimate(bpm, (), 0.0, "fallback")
    interval = 60.0 / bpm
    beat_count = max(1, int(duration_seconds / interval))
    return BeatEstimate(
        bpm=bpm,
        beat_times=tuple(index * interval for index in range(beat_count)),
        confidence=0.0,
        source="fallback",
    )


def estimate_beats(
    samples: Sequence[float],
    sample_rate: int,
    *,
    fallback_bpm: float = 120.0,
) -> BeatEstimate:
    """Estimate BPM/beat times, falling back cleanly when librosa is absent."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if fallback_bpm <= 0:
        raise ValueError("fallback_bpm must be positive")
    duration = len(samples) / sample_rate
    try:
        import librosa
        import numpy as np
    except ImportError:
        return _fallback_beats(duration, fallback_bpm)

    if not samples:
        return _fallback_beats(duration, fallback_bpm)
    signal = np.asarray(samples, dtype=np.float32)
    try:
        tempo, beat_frames = librosa.beat.beat_track(y=signal, sr=sample_rate, units="frames")
        bpm_value = float(np.asarray(tempo).reshape(-1)[0])
        if bpm_value <= 0:
            return _fallback_beats(duration, fallback_bpm)
        times = librosa.frames_to_time(beat_frames, sr=sample_rate)
        beat_times = tuple(float(value) for value in np.asarray(times).reshape(-1))
    except (RuntimeError, ValueError, TypeError):
        return _fallback_beats(duration, fallback_bpm)
    confidence = min(1.0, len(beat_times) / max(1.0, duration * bpm_value / 60.0))
    return BeatEstimate(bpm_value, beat_times, confidence, "librosa")


def seconds_to_ticks(seconds: float, bpm: float, ppq: int) -> int:
    """Convert analysis seconds to the internal integer tick representation."""
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    if bpm <= 0 or ppq <= 0:
        raise ValueError("bpm and ppq must be positive")
    return round(seconds * bpm * ppq / 60.0)
