import array
import hashlib
import json
import wave
from pathlib import Path

import pytest

from siegfridi.core.models import Note, Project, Track
from siegfridi.sound import SoundPackError, SoundPackManifest, get_style_preset
from siegfridi.synthesis import (
    SynthesisError,
    find_fluidsynth,
    native_fluidsynth_available,
    render_wav,
)


def test_sound_pack_manifest_resolves_and_verifies_hash(tmp_path) -> None:
    soundfont = tmp_path / "custom.sf2"
    soundfont.write_bytes(b"synthetic-soundfont")
    digest = hashlib.sha256(soundfont.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "id": "project-pack",
                "name": "Project Pack",
                "version": "0.1.0",
                "soundfont": soundfont.name,
                "sha256": digest,
                "license": "Original project asset",
                "profiles": [{"id": "lead", "name": "Lead", "program": 80}],
            }
        ),
        encoding="utf-8",
    )

    manifest = SoundPackManifest.load(manifest_path)

    assert manifest.verify(manifest_path) == soundfont.resolve()
    assert manifest.profiles[0].id == "lead"
    soundfont.write_bytes(b"changed")
    with pytest.raises(SoundPackError, match="hash mismatch"):
        manifest.verify(manifest_path)


def test_builtin_style_presets_cover_project_direction() -> None:
    assert get_style_preset("oriental-project").tempo_min == 135
    assert "organ" in get_style_preset("dark-gothic").default_roles
    assert "fm-lead" in get_style_preset("retro-rpg").sound_profile_ids


def test_fluidr3_gm_asset_manifest_is_present_and_verified() -> None:
    manifest_path = Path("assets/packs/fluidr3-gm.json")
    soundfont = Path("assets/packs/FluidR3_GM.sf2")
    if not manifest_path.is_file() or not soundfont.is_file():
        pytest.skip("locally acquired FluidR3_GM asset is unavailable")
    manifest = SoundPackManifest.load(manifest_path)
    assert manifest.verify(manifest_path) == soundfont.resolve()
    assert manifest.license == "MIT"
    assert manifest.source_url and manifest.license_url
    assert {profile.id for profile in manifest.profiles} >= {"cathedral-organ", "lead-synth"}


def test_freepats_ocarina_asset_manifest_is_present_and_verified() -> None:
    manifest_path = Path("assets/packs/freepats-ocarina.json")
    soundfont = Path("assets/packs/Ocarina-20241002.sf2")
    if not manifest_path.is_file() or not soundfont.is_file():
        pytest.skip("locally acquired FreePats Ocarina asset is unavailable")
    manifest = SoundPackManifest.load(manifest_path)
    assert manifest.verify(manifest_path) == soundfont.resolve()
    assert manifest.license == "CC0-1.0"
    assert manifest.source_url and manifest.license_url
    assert manifest.profiles[0].id == "folk-wind"


def test_sp_bamboo_flute_source_manifest_matches_local_files() -> None:
    manifest_path = Path("assets/packs/sp-bamboo-flute-source.json")
    source_root = Path("assets/packs/sources/sp-bamboo-flute")
    if not manifest_path.is_file() or not source_root.is_dir():
        pytest.skip("locally acquired SP Bamboo Flute source is unavailable")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest["files"] or not (source_root / Path(manifest["files"][0]["path"])).is_file():
        pytest.skip("locally acquired SP Bamboo Flute source files are unavailable")
    assert manifest["license"] == "CC0-1.0"
    assert manifest["runtime_supported"] is False
    assert len(manifest["files"]) == manifest["file_count"]
    assert sum(entry["size"] for entry in manifest["files"]) == manifest["payload_bytes"]

    for entry in manifest["files"]:
        path = source_root / Path(entry["path"])
        assert path.is_file(), entry["path"]
        assert path.stat().st_size == entry["size"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_render_reports_missing_fluidsynth_without_touching_project(tmp_path) -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 480, 60)])])
    soundfont = tmp_path / "missing.sf2"
    soundfont.write_bytes(b"not-a-real-soundfont")
    output = tmp_path / "render.wav"

    assert find_fluidsynth(tmp_path / "missing-fluidsynth.exe") is None
    with pytest.raises(SynthesisError, match="FluidSynth executable"):
        render_wav(project, soundfont, output, executable=tmp_path / "missing-fluidsynth.exe")
    assert not output.exists()


def test_native_binding_renders_audible_wav_when_cli_is_unavailable(monkeypatch, tmp_path) -> None:
    soundfont = Path(".venv/Lib/site-packages/pretty_midi/TimGM6mb.sf2")
    if not soundfont.is_file() or not native_fluidsynth_available():
        pytest.skip("native FluidSynth or the development SoundFont is unavailable")
    monkeypatch.setattr("siegfridi.synthesis.render.find_fluidsynth", lambda _executable=None: None)
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 480, 60)])])
    output = render_wav(project, soundfont, tmp_path / "native.wav", sample_rate=8000)

    with wave.open(str(output), "rb") as wav_file:
        samples = array.array("h")
        samples.frombytes(wav_file.readframes(wav_file.getnframes()))
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
    assert max(abs(value) for value in samples) > 100
