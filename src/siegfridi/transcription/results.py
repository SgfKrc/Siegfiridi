"""Stable transcription result types independent of the model backend."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..core.models import Note, Project, Track
from .beat import seconds_to_ticks


@dataclass(frozen=True, slots=True)
class CandidateNote:
    start_seconds: float
    end_seconds: float
    pitch: int
    confidence: float
    velocity: int = 100
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("candidate note times are invalid")
        if not 0 <= self.pitch <= 127:
            raise ValueError("pitch must be between 0 and 127")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not 1 <= self.velocity <= 127:
            raise ValueError("velocity must be between 1 and 127")


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    notes: tuple[CandidateNote, ...]
    bpm: float
    sample_rate: int
    source: str
    model_version: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.bpm <= 0 or self.sample_rate <= 0:
            raise ValueError("bpm and sample_rate must be positive")

    def filtered(self, minimum_confidence: float = 0.5) -> TranscriptionResult:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")
        return TranscriptionResult(
            notes=tuple(note for note in self.notes if note.confidence >= minimum_confidence),
            bpm=self.bpm,
            sample_rate=self.sample_rate,
            source=self.source,
            model_version=self.model_version,
            warnings=self.warnings,
        )

    def to_project(
        self,
        *,
        ppq: int = 480,
        track_name: str = "Transcription candidate",
        role: str = "candidate",
        minimum_confidence: float = 0.0,
    ) -> Project:
        """Map accepted candidates into the common tick/PPQ project model."""
        selected = self.filtered(minimum_confidence).notes
        notes = [
            Note(
                start_tick=seconds_to_ticks(item.start_seconds, self.bpm, ppq),
                duration_tick=max(
                    1,
                    seconds_to_ticks(item.end_seconds - item.start_seconds, self.bpm, ppq),
                ),
                pitch=item.pitch,
                velocity=item.velocity,
            )
            for item in selected
        ]
        return Project(ppq=ppq, tempo_bpm=self.bpm, tracks=[Track(track_name, role, notes=notes)])


def _value(event: Any, names: Sequence[str], default: Any = None) -> Any:
    if isinstance(event, Mapping):
        for name in names:
            if name in event:
                return event[name]
        return default
    for name in names:
        if hasattr(event, name):
            return getattr(event, name)
    return default


def parse_note_events(events: Iterable[Any], source: str = "basic-pitch") -> tuple[CandidateNote, ...]:
    """Normalize Basic Pitch tuple/dict/object events into stable candidates."""
    result: list[CandidateNote] = []
    for event in events:
        if isinstance(event, (tuple, list)):
            if len(event) < 3:
                continue
            start, end, pitch = event[:3]
            amplitude = event[3] if len(event) > 3 else 1.0
            # Basic Pitch stores optional pitch-bend values in field 5, not
            # confidence. Until a backend exposes confidence explicitly, use
            # normalized amplitude as the candidate confidence.
            confidence = event[4] if len(event) > 4 and isinstance(event[4], (int, float)) else amplitude
        else:
            start = _value(event, ("start_time", "start", "onset"))
            end = _value(event, ("end_time", "end", "offset"))
            pitch = _value(event, ("pitch", "midi_pitch", "note"))
            amplitude = _value(event, ("amplitude", "velocity"), 1.0)
            confidence = _value(event, ("confidence", "probability"), amplitude)
        try:
            start_value = float(start)
            end_value = float(end)
            pitch_value = round(float(pitch))
            confidence_value = max(0.0, min(1.0, float(confidence)))
            amplitude_value = float(amplitude)
            velocity = round(amplitude_value * 127) if 0.0 <= amplitude_value <= 1.0 else round(amplitude_value)
            result.append(
                CandidateNote(
                    start_seconds=start_value,
                    end_seconds=end_value,
                    pitch=pitch_value,
                    confidence=confidence_value,
                    velocity=max(1, min(127, velocity)),
                    source=source,
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(sorted(result, key=lambda item: (item.start_seconds, item.pitch, item.end_seconds)))
