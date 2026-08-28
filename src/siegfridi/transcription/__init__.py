"""Beat tracking and optional Basic Pitch transcription adapters."""

from .basic_pitch import TranscriptionDependencyError, transcribe_file
from .beat import BeatEstimate, estimate_beats, seconds_to_ticks
from .importer import (
    CandidateSummary,
    append_result_track,
    candidate_to_note,
    result_to_track,
    summarize_candidates,
)
from .results import CandidateNote, TranscriptionResult, parse_note_events

__all__ = [
    "BeatEstimate",
    "CandidateNote",
    "CandidateSummary",
    "TranscriptionDependencyError",
    "TranscriptionResult",
    "append_result_track",
    "candidate_to_note",
    "estimate_beats",
    "parse_note_events",
    "result_to_track",
    "seconds_to_ticks",
    "summarize_candidates",
    "transcribe_file",
]
