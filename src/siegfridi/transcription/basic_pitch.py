"""Optional Spotify Basic Pitch adapter behind a stable project API."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from ..audio.decoder import AudioCache, decode_audio
from .beat import estimate_beats
from .results import TranscriptionResult, parse_note_events


class TranscriptionDependencyError(RuntimeError):
    """Raised when the optional transcription model cannot be loaded."""


def _prediction_events(prediction: Any) -> Any:
    if isinstance(prediction, tuple) and len(prediction) >= 3:
        return prediction[2]
    if isinstance(prediction, dict):
        return prediction.get("note_events", ())
    return getattr(prediction, "note_events", prediction)


def transcribe_file(
    audio_path: str | Path,
    *,
    model_path: str | Path | None = None,
    cache: AudioCache | None = None,
    target_rate: int = 22050,
) -> TranscriptionResult:
    """Run Basic Pitch once and normalize its note events for the editor."""
    audio_source = Path(audio_path)
    if not audio_source.is_file():
        raise FileNotFoundError(audio_source)
    try:
        basic_pitch = importlib.import_module("basic_pitch")
        inference = importlib.import_module("basic_pitch.inference")
    except (ImportError, AttributeError, ValueError, TypeError, OSError, RuntimeError) as exc:
        # 导入 Basic Pitch / tensorflow 时可能因依赖冲突（如 numpy 2.x 与
        # tensorflow<2.16 不兼容、缺少 tflite-runtime 等）抛非 ImportError。
        # 统一降级为结构化依赖错误，交由 worker 边界返回给 UI。
        raise TranscriptionDependencyError(
            "Basic Pitch is not usable; install a compatible transcription extra"
        ) from exc

    model = model_path or getattr(basic_pitch, "ICASSP_2022_MODEL_PATH", None)
    if model is None:
        raise TranscriptionDependencyError("Basic Pitch model path is unavailable")
    predict = getattr(inference, "predict", None)
    if predict is None:
        raise TranscriptionDependencyError("installed Basic Pitch has no inference.predict")

    audio = decode_audio(audio_path, target_rate=target_rate, cache=cache)
    beats = estimate_beats(audio.samples, audio.sample_rate)
    try:
        prediction = predict(str(audio_source), model)
    except (OSError, RuntimeError, ValueError) as exc:
        raise TranscriptionDependencyError(f"Basic Pitch inference failed: {exc}") from exc
    candidates = parse_note_events(_prediction_events(prediction))
    warnings = () if beats.source == "librosa" else ("tempo estimated by fallback",)
    version = getattr(basic_pitch, "__version__", None)
    return TranscriptionResult(
        notes=candidates,
        bpm=beats.bpm,
        sample_rate=audio.sample_rate,
        source="basic-pitch",
        model_version=str(version) if version is not None else None,
        warnings=warnings,
    )
