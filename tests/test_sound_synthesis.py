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
    render_manifest,
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


def test_oriental_project_asset_manifest_is_original_and_verified() -> None:
    manifest_path = Path("assets/packs/oriental-project-v01.json")
    soundfont = Path("assets/packs/oriental-project-v0.1.sf2")
    if not manifest_path.is_file() or not soundfont.is_file():
        pytest.skip("generated Oriental Project asset is unavailable")
    manifest = SoundPackManifest.load(manifest_path)
    assert manifest.verify(manifest_path) == soundfont.resolve()
    assert manifest.license == "CC0-1.0"
    assert manifest.redistributable is True
    assert manifest.profiles[0].id == "zunpet-trumpet"
    assert {profile.id for profile in manifest.profiles} >= {"fm-lead", "folk-wind", "sampled-drums"}


def test_oriental_project_manifest_renders_with_profile_routing(monkeypatch, tmp_path) -> None:
    manifest_path = Path("assets/packs/oriental-project-v01.json")
    soundfont = Path("assets/packs/oriental-project-v0.1.sf2")
    if not manifest_path.is_file() or not soundfont.is_file() or not native_fluidsynth_available():
        pytest.skip("generated Oriental Project asset or native FluidSynth is unavailable")
    monkeypatch.setattr("siegfridi.synthesis.render.find_fluidsynth", lambda _executable=None: None)
    project = Project(
        tempo_bpm=150,
        tracks=[
            Track("Brass", sound_profile_id="zunpet-trumpet", notes=[Note(0, 480, 72, 110)]),
            Track("FM", sound_profile_id="fm-lead", notes=[Note(0, 480, 60, 90)]),
        ],
    )
    output = render_manifest(project, manifest_path, tmp_path / "oriental.wav", sample_rate=8000)
    with wave.open(str(output), "rb") as wav_file:
        samples = array.array("h")
        samples.frombytes(wav_file.readframes(wav_file.getnframes()))
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
    assert max(abs(value) for value in samples) > 100


def test_dark_gothic_asset_manifest_is_original_and_renders_all_roles(monkeypatch, tmp_path) -> None:
    manifest_path = Path("assets/packs/dark-gothic-v01.json")
    soundfont = Path("assets/packs/dark-gothic-v0.1.sf2")
    if not manifest_path.is_file() or not soundfont.is_file() or not native_fluidsynth_available():
        pytest.skip("generated Dark Gothic asset or native FluidSynth is unavailable")
    manifest = SoundPackManifest.load(manifest_path)
    assert manifest.verify(manifest_path) == soundfont.resolve()
    assert manifest.license == "CC0-1.0"
    assert manifest.redistributable is True
    assert {profile.id for profile in manifest.profiles} >= {
        "cathedral-organ",
        "dark-choir",
        "bell",
        "bowed-bass",
        "plucked-relic",
        "gothic-percussion",
    }
    monkeypatch.setattr("siegfridi.synthesis.render.find_fluidsynth", lambda _executable=None: None)
    project = Project(
        tempo_bpm=100,
        tracks=[
            Track("Organ", sound_profile_id="cathedral-organ", notes=[Note(0, 480, 48, 105)]),
            Track("Choir", sound_profile_id="dark-choir", notes=[Note(0, 480, 60, 92)]),
            Track("Bell", sound_profile_id="bell", notes=[Note(0, 480, 72, 110)]),
            Track("Strings", sound_profile_id="bowed-bass", notes=[Note(0, 480, 43, 88)]),
            Track("Pluck", sound_profile_id="plucked-relic", notes=[Note(0, 480, 67, 100)]),
            Track("Percussion", sound_profile_id="gothic-percussion", notes=[Note(0, 240, 36, 115)]),
        ],
    )
    output = render_manifest(project, manifest_path, tmp_path / "gothic.wav", sample_rate=8000)
    with wave.open(str(output), "rb") as wav_file:
        samples = array.array("h")
        samples.frombytes(wav_file.readframes(wav_file.getnframes()))
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
    assert max(abs(value) for value in samples) > 100


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


def test_render_wav_validates_inputs(tmp_path) -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 480, 60)])])
    soundfont = tmp_path / "sf.sf2"
    soundfont.write_bytes(b"fake")

    with pytest.raises(ValueError, match="sample_rate must be positive"):
        render_wav(project, soundfont, tmp_path / "out.wav", sample_rate=0)
    with pytest.raises(FileNotFoundError):
        render_wav(project, tmp_path / "missing.sf2", tmp_path / "out.wav")


def test_render_wav_reports_cli_failure_and_missing_output(monkeypatch, tmp_path) -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 480, 60)])])
    soundfont = tmp_path / "sf.sf2"
    soundfont.write_bytes(b"fake")
    executable = tmp_path / "fluidsynth.exe"
    executable.write_bytes(b"MZ")


    class _Failure:
        returncode = 1
        stderr = "boom: bad soundfont"
        stdout = ""

    monkeypatch.setattr(
        "siegfridi.synthesis.render.subprocess.run", lambda *_a, **_k: _Failure()
    )
    with pytest.raises(SynthesisError, match="FluidSynth rendering failed"):
        render_wav(project, soundfont, tmp_path / "out.wav", executable=executable)

    class _NoOutput:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr(
        "siegfridi.synthesis.render.subprocess.run", lambda *_a, **_k: _NoOutput()
    )
    with pytest.raises(SynthesisError, match="did not create a WAV"):
        render_wav(project, soundfont, tmp_path / "out2.wav", executable=executable)


def test_native_binding_renders_audible_wav_when_cli_is_unavailable(monkeypatch, tmp_path) -> None:
    candidates = (
        Path("assets/packs/FluidR3_GM.sf2"),
        Path(".venv/Lib/site-packages/pretty_midi/TimGM6mb.sf2"),
    )
    soundfont = next((path for path in candidates if path.is_file()), None)
    if soundfont is None or not native_fluidsynth_available():
        pytest.skip("native FluidSynth or a development SoundFont is unavailable")
    monkeypatch.setattr("siegfridi.synthesis.render.find_fluidsynth", lambda _executable=None: None)
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 480, 60)])])
    output = render_wav(project, soundfont, tmp_path / "native.wav", sample_rate=8000)

    with wave.open(str(output), "rb") as wav_file:
        samples = array.array("h")
        samples.frombytes(wav_file.readframes(wav_file.getnframes()))
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
    assert max(abs(value) for value in samples) > 100
