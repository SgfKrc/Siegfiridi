"""FluidSynth command-line renderer with a Python-process fallback boundary."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from types import ModuleType

from ..core.models import Project
from ..midi.files import save_project
from ..playback.player import scheduled_events, tick_to_seconds
from ..sound.packs import SoundPackManifest
from ..sound.profiles import SoundProfile


class SynthesisError(RuntimeError):
    """Raised when SoundFont rendering cannot be started or completed."""


def find_fluidsynth(executable: str | Path | None = None) -> str | None:
    """Find a FluidSynth executable without importing optional native bindings."""
    if executable is not None:
        path = Path(executable)
        return str(path) if path.is_file() else None
    found = shutil.which("fluidsynth")
    if found:
        return found
    configured = os.environ.get("SIEGFRIDI_FLUIDSYNTH")
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path)
    return None


def _load_native_fluidsynth() -> ModuleType | None:
    """Import pyFluidSynth only when CLI rendering is unavailable."""
    try:
        module = importlib.import_module("fluidsynth")
        if not hasattr(module, "Synth"):
            return None
        return module
    except (ImportError, OSError, RuntimeError, AttributeError):
        return None


def native_fluidsynth_available() -> bool:
    """Return whether pyFluidSynth can create a native FluidSynth instance."""
    module = _load_native_fluidsynth()
    if module is None:
        return False
    synth = None
    try:
        synth = module.Synth()
        return True
    except (OSError, RuntimeError, AttributeError, TypeError):
        return False
    finally:
        if synth is not None:
            try:
                synth.delete()
            except (OSError, RuntimeError, AttributeError):
                pass


def _render_wav_native(
    project: Project,
    soundfont_path: Path,
    destination: Path,
    sample_rate: int,
    profiles: dict[str, SoundProfile] | None = None,
) -> Path:
    """Render scheduled note events through the pyFluidSynth audio pull API."""
    module = _load_native_fluidsynth()
    if module is None:
        raise SynthesisError(
            "FluidSynth CLI and Python binding were not found; install FluidSynth and pyfluidsynth"
        )

    try:
        import numpy as np
    except ImportError as exc:
        raise SynthesisError("NumPy is required for Python FluidSynth rendering") from exc

    synth = None
    try:
        synth = module.Synth(samplerate=sample_rate)
        loaded_id = synth.sfload(str(soundfont_path))
        try:
            soundfont_id = int(loaded_id)
        except (TypeError, ValueError) as exc:
            raise SynthesisError(f"FluidSynth returned an invalid SoundFont id: {loaded_id!r}") from exc
        if soundfont_id < 0:
            raise SynthesisError(f"FluidSynth could not load SoundFont: {soundfont_path}")

        chunks: list[np.ndarray] = []
        cursor = 0
        events = scheduled_events(project)
        configured_channels: set[int] = set()
        for event in events:
            channel = event.message.channel
            if channel in configured_channels:
                continue
            track = project.tracks[event.track_index]
            profile = profiles.get(track.sound_profile_id) if profiles and track.sound_profile_id else None
            if profile is not None:
                synth.program_select(channel, soundfont_id, profile.bank, profile.program)
            else:
                synth.program_select(channel, soundfont_id, 0, 0)
            if track.volume != 1.0:
                synth.cc(channel, 7, round(track.volume * 127))
            if track.pan != 0.0:
                synth.cc(channel, 10, round((track.pan + 1.0) * 63.5))
            configured_channels.add(channel)
        for event in events:
            frame = round(tick_to_seconds(event.tick, project.ppq, project.tempo_bpm) * sample_rate)
            if frame > cursor:
                chunks.append(np.asarray(synth.get_samples(frame - cursor), dtype=np.int16))
                cursor = frame
            message = event.message
            if message.type == "note_on" and message.velocity:
                synth.noteon(message.channel, message.note, message.velocity)
            else:
                synth.noteoff(message.channel, message.note)

        # Give the last notes time to release before closing the synth.
        tail_frames = max(sample_rate // 2, 1)
        chunks.append(np.asarray(synth.get_samples(tail_frames), dtype=np.int16))
        samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
        if samples.size % 2:
            samples = samples[:-1]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())
    except SynthesisError:
        raise
    except (OSError, RuntimeError, AttributeError, TypeError, ValueError) as exc:
        raise SynthesisError(f"Python FluidSynth rendering failed: {exc}") from exc
    finally:
        if synth is not None:
            try:
                synth.delete()
            except (OSError, RuntimeError, AttributeError):
                pass
    if not destination.is_file() or destination.stat().st_size == 0:
        raise SynthesisError(f"FluidSynth did not create a WAV file: {destination}")
    return destination


def render_wav(
    project: Project,
    soundfont: str | Path,
    output_path: str | Path,
    *,
    executable: str | Path | None = None,
    sample_rate: int = 44100,
    profiles: dict[str, SoundProfile] | None = None,
) -> Path:
    """Render a project to WAV, preferring CLI and falling back to pyFluidSynth."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    soundfont_path = Path(soundfont)
    if not soundfont_path.is_file():
        raise FileNotFoundError(soundfont_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fluidsynth = find_fluidsynth(executable)
    if fluidsynth is None:
        if executable is not None:
            raise SynthesisError("FluidSynth executable was not found; install FluidSynth and retry")
        return _render_wav_native(project, soundfont_path, destination, sample_rate, profiles)
    with tempfile.TemporaryDirectory(prefix="siegfridi-render-") as directory:
        midi_path = Path(directory) / "project.mid"
        save_project(project, midi_path, profiles)
        command = [
            fluidsynth,
            "-ni",
            "-F",
            str(destination),
            "-r",
            str(sample_rate),
            str(soundfont_path),
            str(midi_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise SynthesisError(f"FluidSynth rendering failed ({completed.returncode}): {detail}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise SynthesisError(f"FluidSynth did not create a WAV file: {destination}")
    return destination


def render_manifest(
    project: Project,
    manifest_path: str | Path,
    output_path: str | Path,
    *,
    executable: str | Path | None = None,
    sample_rate: int = 44100,
) -> Path:
    """Verify a SoundFont manifest then render with its referenced asset."""
    manifest = SoundPackManifest.load(manifest_path)
    soundfont = manifest.verify(manifest_path)
    return render_wav(
        project,
        soundfont,
        output_path,
        executable=executable,
        sample_rate=sample_rate,
        profiles={profile.id: profile for profile in manifest.profiles},
    )
