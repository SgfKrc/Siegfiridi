"""Validation and branch tests for transcription results, parsing and beat estimation."""

import pytest

from siegfridi.transcription import (
    TranscriptionResult,
    estimate_beats,
    parse_note_events,
    seconds_to_ticks,
)
from siegfridi.transcription.results import CandidateNote


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_seconds": -1, "end_seconds": 1, "pitch": 60, "confidence": 0.5}, "candidate note times"),
        ({"start_seconds": 1, "end_seconds": 1, "pitch": 60, "confidence": 0.5}, "candidate note times"),
        ({"start_seconds": 0, "end_seconds": 1, "pitch": 128, "confidence": 0.5}, "pitch must be between"),
        ({"start_seconds": 0, "end_seconds": 1, "pitch": -1, "confidence": 0.5}, "pitch must be between"),
        ({"start_seconds": 0, "end_seconds": 1, "pitch": 60, "confidence": 1.5}, "confidence must be between"),
        ({"start_seconds": 0, "end_seconds": 1, "pitch": 60, "confidence": -0.1}, "confidence must be between"),
        ({"start_seconds": 0, "end_seconds": 1, "pitch": 60, "confidence": 0.5, "velocity": 0}, "velocity must be between"),
        ({"start_seconds": 0, "end_seconds": 1, "pitch": 60, "confidence": 0.5, "velocity": 128}, "velocity must be between"),
    ],
)
def test_candidate_note_validation(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        CandidateNote(**kwargs)


def test_transcription_result_validation_and_filtering() -> None:
    with pytest.raises(ValueError, match="bpm and sample_rate"):
        TranscriptionResult(notes=(), bpm=0, sample_rate=22050, source="test")
    with pytest.raises(ValueError, match="minimum_confidence"):
        TranscriptionResult(notes=(), bpm=120, sample_rate=22050, source="test").filtered(1.5)

    notes = (
        CandidateNote(0.0, 0.5, 60, 0.9, 100),
        CandidateNote(0.5, 1.0, 64, 0.2, 80),
    )
    result = TranscriptionResult(notes=notes, bpm=120, sample_rate=22050, source="test")

    filtered = result.filtered(0.5)
    assert [note.pitch for note in filtered.notes] == [60]
    assert filtered.source == "test"


def test_parse_note_events_handles_tuple_dict_and_object() -> None:
    class _Event:
        start_time = 0.25
        end_time = 0.75
        pitch = 72
        amplitude = 0.5

    events = parse_note_events(
        [
            (0.0, 0.25, 60, 0.8, 0.95),  # tuple with explicit confidence
            {"start_time": 0.5, "end_time": 1.0, "pitch": 64, "amplitude": 0.4},  # dict, no confidence
            _Event(),  # object attributes
            (1.0, 65),  # too short -> skipped
            (0.0, 0.5, "bad"),  # bad pitch -> skipped
        ]
    )

    assert [(note.pitch, note.start_seconds) for note in events] == [(60, 0.0), (72, 0.25), (64, 0.5)]
    assert events[0].confidence == 0.95  # explicit confidence wins
    assert events[1].confidence == pytest.approx(0.5)  # object amplitude
    assert events[2].confidence == pytest.approx(0.4)  # falls back to amplitude


def test_parse_note_events_sorts_and_clips_confidence() -> None:
    events = parse_note_events(
        [
            (0.5, 1.0, 64, 0.4, 1.5),  # confidence clipped to 1.0
            (0.0, 0.5, 60, 0.8, -0.5),  # confidence clipped to 0.0
        ]
    )

    assert [note.start_seconds for note in events] == [0.0, 0.5]
    assert events[0].confidence == 0.0
    assert events[1].confidence == 1.0


def test_estimate_beats_validates_arguments_and_empty_samples() -> None:
    with pytest.raises(ValueError, match="sample_rate must be positive"):
        estimate_beats([0.0] * 100, 0)
    with pytest.raises(ValueError, match="fallback_bpm"):
        estimate_beats([0.0] * 100, 44100, fallback_bpm=0)

    estimate = estimate_beats([], 44100, fallback_bpm=100)
    assert estimate.source == "fallback"
    assert estimate.bpm == 100


def test_estimate_beats_uses_librosa_when_available() -> None:
    # 本机装有 librosa（audio extra）：一段 2 秒 44100Hz 静音以确定性方式走 librosa 或 fallback。
    estimate = estimate_beats([0.0] * 88200, 44100, fallback_bpm=100)

    if estimate.source == "librosa":
        assert estimate.bpm > 0
        assert all(t >= 0 for t in estimate.beat_times)
        assert 0.0 <= estimate.confidence <= 1.0
    else:
        assert estimate.source == "fallback"


def test_seconds_to_ticks_validation() -> None:
    with pytest.raises(ValueError, match="seconds must be non-negative"):
        seconds_to_ticks(-0.1, 120, 480)
    with pytest.raises(ValueError, match="bpm and ppq"):
        seconds_to_ticks(1.0, 0, 480)
    with pytest.raises(ValueError, match="bpm and ppq"):
        seconds_to_ticks(1.0, 120, 0)
    assert seconds_to_ticks(0.5, 120, 480) == 480