"""Beat tracking and optional Basic Pitch transcription adapters."""

from .basic_pitch import TranscriptionDependencyError, transcribe_file
from .beat import BeatEstimate, estimate_beats, seconds_to_ticks
from .results import CandidateNote, TranscriptionResult, parse_note_events

__all__ = [
    "BeatEstimate",
    "CandidateNote",
    "TranscriptionDependencyError",
    "TranscriptionResult",
    "estimate_beats",
    "parse_note_events",
    "seconds_to_ticks",
    "transcribe_file",
]
