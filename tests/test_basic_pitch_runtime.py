import math
import struct
import wave
from types import SimpleNamespace

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


def test_basic_pitch_normalizes_supported_prediction_shapes(monkeypatch, tmp_path) -> None:
    source = tmp_path / "fake.wav"
    source.write_bytes(b"placeholder")
    prediction = {
        "note_events": [
            {"start_time": 0.0, "end_time": 0.25, "pitch": 60, "confidence": 0.9}
        ]
    }
    fake_basic_pitch = SimpleNamespace(ICASSP_2022_MODEL_PATH="default-model", __version__="1.2")
    fake_inference = SimpleNamespace(predict=lambda path, model: prediction)
    modules = {"basic_pitch": fake_basic_pitch, "basic_pitch.inference": fake_inference}
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.importlib.import_module",
        lambda name: modules[name],
    )
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.decode_audio",
        lambda *_args, **_kwargs: SimpleNamespace(samples=(0.0,), sample_rate=22050),
    )
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.estimate_beats",
        lambda *_args, **_kwargs: SimpleNamespace(bpm=120, source="librosa"),
    )

    result = transcribe_file(source)

    assert result.model_version == "1.2"
    assert result.warnings == ()
    assert result.notes[0].pitch == 60


def test_basic_pitch_wraps_import_and_inference_failures(monkeypatch, tmp_path) -> None:
    source = tmp_path / "fake.wav"
    source.write_bytes(b"placeholder")

    def import_failure(name):
        raise RuntimeError(f"broken {name}")

    monkeypatch.setattr("siegfridi.transcription.basic_pitch.importlib.import_module", import_failure)
    with pytest.raises(TranscriptionDependencyError, match="not usable"):
        transcribe_file(source)

    fake_basic_pitch = SimpleNamespace(ICASSP_2022_MODEL_PATH="model")
    fake_inference = SimpleNamespace(predict=lambda *_args: (_ for _ in ()).throw(RuntimeError("inference down")))
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.importlib.import_module",
        lambda name: {"basic_pitch": fake_basic_pitch, "basic_pitch.inference": fake_inference}[name],
    )
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.decode_audio",
        lambda *_args, **_kwargs: SimpleNamespace(samples=(0.0,), sample_rate=22050),
    )
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.estimate_beats",
        lambda *_args, **_kwargs: SimpleNamespace(bpm=120, source="fallback"),
    )
    with pytest.raises(TranscriptionDependencyError, match="inference failed"):
        transcribe_file(source)


@pytest.mark.parametrize(
    ("basic_pitch_module", "inference_module", "message"),
    [
        (SimpleNamespace(), SimpleNamespace(predict=lambda *_args: ()), "model path"),
        (SimpleNamespace(ICASSP_2022_MODEL_PATH="model"), SimpleNamespace(), "inference.predict"),
    ],
)
def test_basic_pitch_rejects_incomplete_installs(
    monkeypatch, tmp_path, basic_pitch_module, inference_module, message
) -> None:
    source = tmp_path / "fake.wav"
    source.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "siegfridi.transcription.basic_pitch.importlib.import_module",
        lambda name: {"basic_pitch": basic_pitch_module, "basic_pitch.inference": inference_module}[name],
    )
    with pytest.raises(TranscriptionDependencyError, match=message):
        transcribe_file(source)
