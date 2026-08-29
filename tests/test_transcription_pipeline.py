import struct
import time
import wave
from types import SimpleNamespace

import pytest

from siegfridi.audio import AudioCache, decode_audio
from siegfridi.core.models import Note
from siegfridi.transcription import (
    TranscriptionResult,
    estimate_beats,
    parse_note_events,
    seconds_to_ticks,
)
from siegfridi.workers import TranscriptionProcess, TranscriptionRequest, run_transcription_job


def _write_wav(path) -> None:
    samples = [0, 8192, -8192, 16384, -16384, 0, 4096, -4096]
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def test_wav_decode_is_cached_and_resampled(tmp_path) -> None:
    source = tmp_path / "sample.wav"
    _write_wav(source)
    cache = AudioCache(tmp_path / "cache")

    decoded = decode_audio(source, target_rate=4000, cache=cache)
    cached = decode_audio(source, target_rate=4000, cache=cache)

    # decode_audio 优先使用 PyAV（audio extra），仅在 PyAV 不可用时回退 WAVE，
    # 因此断言需兼容两种解码器。
    assert decoded.metadata.decoder in {"wave", "pyav"}
    assert decoded.sample_rate == 4000
    assert decoded.metadata.channels == 1
    assert decoded.metadata.duration_seconds == 8 / 8000
    assert decoded.samples == cached.samples
    assert len(list((tmp_path / "cache").glob("*.f32"))) == 1


def test_fallback_beats_and_tick_conversion_are_deterministic() -> None:
    estimate = estimate_beats([0.0] * 88200, 44100, fallback_bpm=100)

    assert estimate.source == "fallback"
    assert estimate.bpm == 100
    assert estimate.beat_times[1] == 0.6
    assert seconds_to_ticks(0.5, 120, 480) == 480


def test_candidate_mapping_preserves_confidence_until_threshold() -> None:
    candidates = parse_note_events(
        [
            {"start_time": 0.0, "end_time": 0.5, "pitch": 60, "amplitude": 0.8, "confidence": 0.95},
            (0.5, 1.0, 64, 0.4, [0, 1, -1]),
        ]
    )
    result = TranscriptionResult(
        notes=candidates,
        bpm=120,
        sample_rate=22050,
        source="test",
    )

    assert candidates[0].velocity == 102
    assert len(result.filtered(0.5).notes) == 1
    project = result.to_project(minimum_confidence=0.5)
    assert project.tracks[0].notes == [Note(0, 480, 60, 102)]


def test_worker_returns_structured_failure_without_model() -> None:
    response = run_transcription_job(TranscriptionRequest("missing.wav"))

    assert response["type"] == "failed"
    assert response["error_type"] in {"TranscriptionDependencyError", "FileNotFoundError"}


def test_worker_emits_structured_success(monkeypatch, tmp_path) -> None:
    result = object()
    calls = []

    class MessageSink:
        def __init__(self) -> None:
            self.items = []

        def put(self, payload) -> None:
            self.items.append(payload)

    messages = MessageSink()

    def fake_transcribe(path, **kwargs):
        calls.append((path, kwargs))
        return result

    monkeypatch.setattr("siegfridi.workers.transcription.transcribe_file", fake_transcribe)
    response = run_transcription_job(
        TranscriptionRequest("song.wav", model_path="model.tflite", cache_dir=str(tmp_path), target_rate=16000),
        messages,
    )

    assert response == {"type": "completed", "result": result}
    assert messages.items[0] == {"type": "started", "audio_path": "song.wav"}
    assert messages.items[1] == response
    assert calls[0][0] == "song.wav"
    assert calls[0][1]["model_path"] == "model.tflite"
    assert calls[0][1]["target_rate"] == 16000
    assert calls[0][1]["cache"].directory == tmp_path


def test_worker_poll_and_cancel_are_safe_without_a_started_process() -> None:
    worker = TranscriptionProcess(TranscriptionRequest("missing.wav"))
    try:
        assert worker.poll() == []
        worker.cancel()
    finally:
        worker.close()


def test_worker_cancel_terminates_a_live_process(monkeypatch) -> None:
    worker = TranscriptionProcess(TranscriptionRequest("missing.wav"))
    events = []
    fake_process = SimpleNamespace(
        is_alive=lambda: True,
        terminate=lambda: events.append("terminate"),
        join=lambda timeout=None: events.append(("join", timeout)),
    )
    worker._process = fake_process

    worker.cancel()

    assert events == ["terminate", ("join", 1.0)]
    assert worker._process is None
    worker.close()


def test_worker_process_can_be_cancelled_or_report_failure() -> None:
    worker = TranscriptionProcess(TranscriptionRequest("missing.wav"))
    worker.start()
    messages: list[dict] = []
    deadline = time.monotonic() + 5.0
    try:
        while time.monotonic() < deadline and worker.is_running:
            messages.extend(worker.poll())
            if any(item["type"] in {"failed", "completed"} for item in messages):
                break
            time.sleep(0.02)
        messages.extend(worker.wait(timeout=1.0))
    finally:
        worker.close()

    assert any(item["type"] == "started" for item in messages)
    assert any(item["type"] == "failed" for item in messages)


def test_worker_context_manager_starts_and_closes(monkeypatch) -> None:
    worker = TranscriptionProcess(TranscriptionRequest("missing.wav"))
    started = []

    monkeypatch.setattr(worker, "start", lambda: started.append(True))
    monkeypatch.setattr(worker, "close", lambda: started.append(False))
    with worker as entered:
        assert entered is worker
    assert started == [True, False]


def test_worker_start_rejects_duplicate_running_process(monkeypatch) -> None:
    worker = TranscriptionProcess(TranscriptionRequest("missing.wav"))
    monkeypatch.setattr(type(worker), "is_running", property(lambda _self: True))

    with pytest.raises(RuntimeError, match="already running"):
        worker.start()
