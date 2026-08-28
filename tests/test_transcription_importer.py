import pytest

from siegfridi.core.models import Note, Project, Track
from siegfridi.transcription import (
    CandidateNote,
    TranscriptionResult,
    append_result_track,
    candidate_to_note,
    result_to_track,
    summarize_candidates,
)


def _result() -> TranscriptionResult:
    return TranscriptionResult(
        notes=(
            CandidateNote(0.0, 0.24, 60, 0.9, 100),
            CandidateNote(0.5, 1.0, 64, 0.2, 80),
        ),
        bpm=120,
        sample_rate=22050,
        source="song.wav",
    )


def test_candidate_import_summary_and_tick_mapping() -> None:
    result = _result()

    summary = summarize_candidates(result, 0.5)
    note = candidate_to_note(result.notes[0], bpm=120, ppq=480, grid_tick=120)

    assert (summary.total, summary.accepted) == (2, 1)
    assert note == Note(0, 240, 60, 100)


def test_result_to_track_filters_and_quantizes_without_mutation() -> None:
    result = _result()

    track = result_to_track(result, minimum_confidence=0.5, grid_tick=120)

    assert track.name == "Transcription candidate"
    assert track.notes == [Note(0, 240, 60, 100)]
    assert len(result.notes) == 2


def test_append_result_track_updates_default_tempo_only() -> None:
    result = _result()
    project = Project(tracks=[Track("Existing")])
    appended = append_result_track(project, result, minimum_confidence=0.5)

    assert project.tempo_bpm == 120
    assert project.tracks[-1] is appended
    project.tempo_bpm = 90
    append_result_track(project, result, minimum_confidence=0.5)
    assert project.tempo_bpm == 90


def test_result_to_track_rejects_invalid_grid() -> None:
    with pytest.raises(ValueError, match="grid_tick"):
        result_to_track(_result(), grid_tick=-1)
