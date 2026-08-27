import math
import struct
import wave

import pytest

from siegfridi.transcription import TranscriptionDependencyError, transcribe_file


def _write_sine_wav(path) -> None:
    sample_rate = 22050
    duration = 1.5
    frames = [
        round(14000 * math.sin(2 * math.pi * 440.0 * index / sample_rate))
        for index in range(round(sample_rate * duration))
    ]
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(struct.pack(f"<{len(frames)}h", *frames))


def test_basic_pitch_runtime_transcribes_short_mono_wav(tmp_path) -> None:
    source = tmp_path / "a4.wav"
    _write_sine_wav(source)
    try:
        result = transcribe_file(source, target_rate=22050)
    except TranscriptionDependencyError as exc:
        pytest.skip(str(exc))

    assert result.source == "basic-pitch"
    assert result.sample_rate == 22050
    assert result.notes
    assert any(68 <= note.pitch <= 72 for note in result.notes)
