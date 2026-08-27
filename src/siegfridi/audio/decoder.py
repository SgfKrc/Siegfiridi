"""Audio decoding boundary with a small reproducible PCM cache."""

from __future__ import annotations

import hashlib
import json
import struct
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class AudioDependencyError(RuntimeError):
    """Raised when a file format needs an optional decoder that is unavailable."""


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    path: str
    sample_rate: int
    channels: int
    frame_count: int
    duration_seconds: float
    cache_key: str
    decoder: str


@dataclass(frozen=True, slots=True)
class DecodedAudio:
    """Mono floating-point audio used by beat tracking and transcription."""

    samples: tuple[float, ...]
    metadata: AudioMetadata

    @property
    def sample_rate(self) -> int:
        return self.metadata.sample_rate

    @property
    def duration_seconds(self) -> float:
        return self.metadata.duration_seconds

    def as_array(self) -> Any:
        """Return a NumPy view when the audio extra is installed."""
        try:
            import numpy as np
        except ImportError as exc:
            raise AudioDependencyError("NumPy is required for array-based analysis") from exc
        return np.asarray(self.samples, dtype=np.float32)


def _cache_key(path: Path, sample_rate: int) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{sample_rate}".encode()
    return hashlib.sha256(payload).hexdigest()[:24]


class AudioCache:
    """On-disk cache for decoded mono float PCM and its metadata."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _metadata_path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def _samples_path(self, key: str) -> Path:
        return self.directory / f"{key}.f32"

    def load(self, key: str) -> DecodedAudio | None:
        metadata_path = self._metadata_path(key)
        samples_path = self._samples_path(key)
        if not metadata_path.exists() or not samples_path.exists():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = AudioMetadata(**payload)
            raw = samples_path.read_bytes()
            if len(raw) % 4:
                return None
            samples = struct.unpack(f"<{len(raw) // 4}f", raw)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, struct.error):
            return None
        return DecodedAudio(tuple(samples), metadata)

    def save(self, audio: DecodedAudio) -> None:
        key = audio.metadata.cache_key
        raw = struct.pack(f"<{len(audio.samples)}f", *audio.samples)
        self._samples_path(key).write_bytes(raw)
        self._metadata_path(key).write_text(
            json.dumps(asdict(audio.metadata), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def _resample(samples: list[float], source_rate: int, target_rate: int) -> list[float]:
    if source_rate == target_rate or not samples:
        return samples
    output_length = max(1, round(len(samples) * target_rate / source_rate))
    ratio = source_rate / target_rate
    result: list[float] = []
    for index in range(output_length):
        position = index * ratio
        left = min(int(position), len(samples) - 1)
        right = min(left + 1, len(samples) - 1)
        fraction = position - left
        result.append(samples[left] + (samples[right] - samples[left]) * fraction)
    return result


def _decode_wav(path: Path, target_rate: int, key: str) -> DecodedAudio:
    with wave.open(str(path), "rb") as reader:
        source_rate = reader.getframerate()
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        frame_count = reader.getnframes()
        raw = reader.readframes(frame_count)
    if source_rate <= 0 or channels <= 0:
        raise ValueError("WAV header has invalid sample rate or channel count")
    if sample_width not in (1, 2, 3, 4):
        raise ValueError(f"unsupported WAV sample width: {sample_width}")

    bytes_per_frame = channels * sample_width
    mono: list[float] = []
    for offset in range(0, len(raw), bytes_per_frame):
        frame = raw[offset : offset + bytes_per_frame]
        if len(frame) < bytes_per_frame:
            break
        total = 0.0
        for channel in range(channels):
            sample = frame[channel * sample_width : (channel + 1) * sample_width]
            if sample_width == 1:
                value = (sample[0] - 128) / 128.0
            elif sample_width == 2:
                value = int.from_bytes(sample, "little", signed=True) / 32768.0
            elif sample_width == 3:
                integer = int.from_bytes(sample, "little", signed=False)
                if integer & 0x800000:
                    integer -= 1 << 24
                value = integer / 8388608.0
            else:
                value = int.from_bytes(sample, "little", signed=True) / 2147483648.0
            total += value
        mono.append(total / channels)

    resampled = _resample(mono, source_rate, target_rate)
    metadata = AudioMetadata(
        path=str(path.resolve()),
        sample_rate=target_rate,
        channels=channels,
        frame_count=len(resampled),
        duration_seconds=frame_count / source_rate,
        cache_key=key,
        decoder="wave",
    )
    return DecodedAudio(tuple(resampled), metadata)


def _decode_pyav(path: Path, target_rate: int, key: str) -> DecodedAudio:
    try:
        import av
    except ImportError as exc:
        raise AudioDependencyError("PyAV is not installed; install the audio extra") from exc

    container = None
    try:
        from av.audio.resampler import AudioResampler

        container = av.open(str(path))
        stream = next(stream for stream in container.streams if stream.type == "audio")
        source_channels = len(stream.layout.channels) if stream.layout else 1
        source_rate = stream.sample_rate or target_rate
        resampler = AudioResampler(format="fltp", layout="mono", rate=target_rate)
        samples: list[float] = []
        for frame in container.decode(stream):
            converted = resampler.resample(frame)
            converted_frames = converted if isinstance(converted, list) else [converted]
            for converted_frame in converted_frames:
                values = converted_frame.to_ndarray().reshape(-1).tolist()
                samples.extend(float(value) for value in values)
        tail = resampler.resample(None)
        tail_frames = tail if isinstance(tail, list) else [tail]
        for converted_frame in tail_frames:
            if converted_frame is not None:
                samples.extend(float(value) for value in converted_frame.to_ndarray().reshape(-1).tolist())
        duration = float(stream.duration * stream.time_base) if stream.duration else len(samples) / source_rate
    except (StopIteration, av.error.FFmpegError) as exc:
        raise ValueError(f"could not decode audio: {path}") from exc
    finally:
        if container is not None:
            container.close()

    metadata = AudioMetadata(
        path=str(path.resolve()),
        sample_rate=target_rate,
        channels=source_channels,
        frame_count=len(samples),
        duration_seconds=duration,
        cache_key=key,
        decoder="pyav",
    )
    return DecodedAudio(tuple(samples), metadata)


def decode_audio(
    path: str | Path,
    target_rate: int = 22050,
    cache: AudioCache | None = None,
) -> DecodedAudio:
    """Decode an audio file, preferring PyAV and caching the mono result."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if target_rate <= 0:
        raise ValueError("target_rate must be positive")
    key = _cache_key(source, target_rate)
    if cache is not None:
        cached = cache.load(key)
        if cached is not None:
            return cached

    try:
        audio = _decode_pyav(source, target_rate, key)
    except AudioDependencyError:
        if source.suffix.lower() != ".wav":
            raise
        audio = _decode_wav(source, target_rate, key)
    if cache is not None:
        cache.save(audio)
    return audio
