"""Convert pending transcription candidates into editable project tracks."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.models import Note, Project, Track
from .beat import seconds_to_ticks
from .results import CandidateNote, TranscriptionResult


@dataclass(frozen=True, slots=True)
class CandidateSummary:
    """Small UI-safe summary for a pending transcription result."""

    total: int
    accepted: int
    minimum_confidence: float
    bpm: float
    source: str


def summarize_candidates(result: TranscriptionResult, minimum_confidence: float = 0.5) -> CandidateSummary:
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError("minimum_confidence must be between 0 and 1")
    accepted = sum(note.confidence >= minimum_confidence for note in result.notes)
    return CandidateSummary(
        total=len(result.notes),
        accepted=accepted,
        minimum_confidence=minimum_confidence,
        bpm=result.bpm,
        source=result.source,
    )


def candidate_to_note(candidate: CandidateNote, *, bpm: float, ppq: int, grid_tick: int = 0) -> Note:
    """Map one accepted candidate to ticks, optionally snapping both edges."""
    start_tick = seconds_to_ticks(candidate.start_seconds, bpm, ppq)
    duration_tick = max(1, seconds_to_ticks(candidate.end_seconds - candidate.start_seconds, bpm, ppq))
    note = Note(start_tick, duration_tick, candidate.pitch, candidate.velocity)
    if grid_tick > 0:
        note = note.quantized(grid_tick)
    return note


def result_to_track(
    result: TranscriptionResult,
    *,
    ppq: int = 480,
    track_name: str = "Transcription candidate",
    role: str = "candidate",
    minimum_confidence: float = 0.5,
    grid_tick: int = 0,
    sound_profile_id: str | None = None,
) -> Track:
    """Build one editable candidate track without mutating the project."""
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError("minimum_confidence must be between 0 and 1")
    if grid_tick < 0:
        raise ValueError("grid_tick must be non-negative")
    notes = [
        candidate_to_note(candidate, bpm=result.bpm, ppq=ppq, grid_tick=grid_tick)
        for candidate in result.notes
        if candidate.confidence >= minimum_confidence
    ]
    return Track(
        name=track_name,
        role=role,
        sound_profile_id=sound_profile_id,
        notes=sorted(notes, key=lambda note: (note.start_tick, note.pitch, note.duration_tick)),
    )


def append_result_track(
    project: Project,
    result: TranscriptionResult,
    *,
    track_name: str = "Transcription candidate",
    minimum_confidence: float = 0.5,
    grid_tick: int = 0,
    sound_profile_id: str | None = None,
) -> Track:
    """Append an accepted candidate track and return the new track."""
    track = result_to_track(
        result,
        ppq=project.ppq,
        track_name=track_name,
        minimum_confidence=minimum_confidence,
        grid_tick=grid_tick,
        sound_profile_id=sound_profile_id,
    )
    project.tracks.append(track)
    if project.tempo_bpm == 120.0:
        project.tempo_bpm = result.bpm
    return track
