"""Wave-decoder fallback path tests: sample widths, channels and invalid headers."""

import struct
import tempfile
import wave
from pathlib import Path

import pytest

from siegfridi.audio.decoder import _decode_wav, _resample


def _write_wav(path, *, channels=1, sample_width=2, sample_rate=8000, samples_per_channel=8):
    """Write a WAV with one ramp frame per channel; return the path."""
    frames = []
    for index in range(samples_per_channel):
        for _ in range(channels):
            value = index
            if sample_width == 1:
                frames.append((value % 128).to_bytes(1, "little"))
            elif sample_width == 2:
                frames.append(struct.pack("<h", value))
            elif sample_width == 3:
                frames.append(int(value).to_bytes(3, "little", signed=False))
            else:
                frames.append(struct.pack("<i", value))
    raw = b"".join(frames)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        writer.writeframes(raw)
    return path


@pytest.mark.parametrize("sample_width", [1, 2, 3, 4])
def test_decode_wav_all_sample_widths(tmp_path, sample_width: int) -> None:
    source = _write_wav(tmp_path / f"w{sample_width}.wav", sample_width=sample_width)
    decoded = _decode_wav(source, target_rate=8000, key="k")

    assert decoded.metadata.decoder == "wave"
    assert decoded.metadata.sample_rate == 8000
    # 每通道 8 帧 ramped 值，mono 化后仍为 8 个采样
    assert len(decoded.samples) == 8
    assert all(isinstance(value, float) for value in decoded.samples)
    # 首帧值 0:16/32-bit -> 0.0;8-bit 映射 (0-128)/128 -> -1.0;24-bit 值 0 -> 0.0
    expected_first = -1.0 if sample_width == 1 else 0.0
    assert decoded.samples[0] == pytest.approx(expected_first)


def test_decode_wav_stereo_mixes_to_mono(tmp_path) -> None:
    source = _write_wav(tmp_path / "stereo.wav", channels=2)
    decoded = _decode_wav(source, target_rate=8000, key="k")

    assert decoded.metadata.channels == 2
    assert len(decoded.samples) == 8
    # 双声道同值 -> mono 值相等（呈斜坡的中间帧）
    assert decoded.samples[7] == pytest.approx(7 / 32768.0)
    assert decoded.samples[3] == pytest.approx(3 / 32768.0)


def test_decode_wav_resamples_when_rates_differ(tmp_path) -> None:
    source = _write_wav(tmp_path / "rs.wav", sample_rate=8000, samples_per_channel=8)
    decoded = _decode_wav(source, target_rate=4000, key="k")

    assert decoded.metadata.sample_rate == 4000
    assert decoded.metadata.frame_count == 4
    assert decoded.metadata.duration_seconds == 8 / 8000


def test_decode_wav_8bit_has_unsigned_offset(tmp_path) -> None:
    source = _write_wav(tmp_path / "w8.wav", sample_width=1)
    decoded = _decode_wav(source, target_rate=8000, key="k")

    # 8-bit: 值 0 -> (0-128)/128 = -1.0；值 128 -> 0.0；值 129 -> +1/128
    assert decoded.samples[0] == pytest.approx(-1.0)
    # 8-bit 字节值 0..7 全部映射为负值, 验证单调性
    for index in range(1, len(decoded.samples)):
        assert decoded.samples[index] > decoded.samples[index - 1]


def test_decode_wav_rejects_invalid_header(tmp_path) -> None:
    source = tmp_path / "bad.wav"
    source.write_bytes(b"RIFF" + b"\x00" * 40)
    with pytest.raises((ValueError, wave.Error, EOFError)):
        _decode_wav(source, target_rate=8000, key="k")


def test_resample_identity_and_downsample() -> None:
    assert _resample([1.0, 2.0, 3.0, 4.0], 4000, 4000) == [1.0, 2.0, 3.0, 4.0]
    downsampled = _resample([0.0, 100.0, 200.0, 300.0], 8000, 4000)
    assert len(downsampled) == 2
    assert downsampled[0] == 0.0
    # 1:2 降采样为抽取式：position = index * 2，取 samples[2] == 200.0
    assert downsampled[1] == 200.0


def test_resample_upsample_and_empty() -> None:
    upsampled = _resample([0.0, 400.0], 4000, 8000)
    assert len(upsampled) == 4
    assert upsampled[0] == 0.0
    assert upsampled[3] == 400.0
    assert _resample([], 8000, 4000) == []
    assert _resample([5.0], 8000, 4000) == [5.0]


def test_decode_wav_duration_uses_source_rate() -> None:
    """duration_seconds 用源采样率计算(不等目标采样率)。"""
    path = Path(tempfile.gettempdir()) / "dur.wav"
    _write_wav(path, sample_rate=8000, samples_per_channel=8)
    decoded = _decode_wav(path, target_rate=8000, key="k")
    assert decoded.metadata.duration_seconds == 8 / 8000