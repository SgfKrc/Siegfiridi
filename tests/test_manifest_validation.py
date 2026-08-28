"""Validation and error-path tests for SoundPackManifest and FluidSynth discovery."""

import hashlib
import json

import pytest

from siegfridi.sound import SoundPackError, SoundPackManifest
from siegfridi.synthesis import find_fluidsynth


def _manifest_payload(**overrides) -> dict:
    payload = {
        "id": "test-pack",
        "name": "Test Pack",
        "version": "1.0.0",
        "soundfont": "test.sf2",
        "sha256": "a" * 64,
        "license": "CC0-1.0",
    }
    payload.update(overrides)
    return payload


def test_manifest_rejects_empty_id_name_version() -> None:
    for field in ("id", "name", "version"):
        with pytest.raises(ValueError, match="must not be empty"):
            SoundPackManifest.from_dict(_manifest_payload(**{field: ""}))


def test_manifest_rejects_non_sf2_sf3_soundfont() -> None:
    with pytest.raises(ValueError, match=r"\.sf2 or \.sf3"):
        SoundPackManifest.from_dict(_manifest_payload(soundfont="test.wav"))


def test_manifest_rejects_bad_sha256() -> None:
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        SoundPackManifest.from_dict(_manifest_payload(sha256="abc"))
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        SoundPackManifest.from_dict(_manifest_payload(sha256="z" * 64))


def test_manifest_rejects_empty_license() -> None:
    with pytest.raises(ValueError, match="license must not be empty"):
        SoundPackManifest.from_dict(_manifest_payload(license=""))


def test_manifest_metadata_fields_default_to_none() -> None:
    manifest = SoundPackManifest.from_dict(_manifest_payload())

    assert manifest.source_url is None
    assert manifest.license_url is None
    assert manifest.attribution is None
    assert manifest.distribution == "redistributable"
    assert manifest.redistributable is True
    assert manifest.profiles == ()


def test_manifest_metadata_fields_round_trip_from_dict() -> None:
    manifest = SoundPackManifest.from_dict(
        _manifest_payload(
            source_url="https://example.com/source",
            license_url="https://example.com/license",
            attribution="Example Author",
            distribution="local-study-only",
            profiles=[{"id": "lead", "name": "Lead", "program": 80}],
        )
    )

    assert manifest.source_url == "https://example.com/source"
    assert manifest.license_url == "https://example.com/license"
    assert manifest.attribution == "Example Author"
    assert manifest.distribution == "local-study-only"
    assert manifest.redistributable is False
    assert manifest.profiles[0].id == "lead"


def test_manifest_load_reports_missing_and_invalid_files(tmp_path) -> None:
    with pytest.raises(SoundPackError, match="could not read"):
        SoundPackManifest.load(tmp_path / "missing.json")

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SoundPackError, match="could not read"):
        SoundPackManifest.load(bad)

    not_object = tmp_path / "array.json"
    not_object.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(SoundPackError, match="JSON object"):
        SoundPackManifest.load(not_object)

    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"id": "x"}), encoding="utf-8")
    with pytest.raises(SoundPackError, match="invalid sound pack manifest"):
        SoundPackManifest.load(invalid)


def test_manifest_resolve_soundfont_requires_existing_file(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload(soundfont="absent.sf2")), encoding="utf-8"
    )
    manifest = SoundPackManifest.load(manifest_path)

    with pytest.raises(SoundPackError, match="does not exist"):
        manifest.resolve_soundfont(manifest_path)


def _write_sf2(path, content: bytes) -> None:
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def test_manifest_load_sound_pack_wrapper(tmp_path) -> None:
    digest = _write_sf2(tmp_path / "test.sf2", b"synthetic-soundfont")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload(sha256=digest)), encoding="utf-8"
    )

    from siegfridi.sound import load_sound_pack

    assert load_sound_pack(manifest_path).verify(manifest_path).name == "test.sf2"


def test_find_fluidsynth_accepts_only_existing_executable(tmp_path) -> None:
    existing = tmp_path / "fluidsynth.exe"
    existing.write_bytes(b"MZ")

    assert find_fluidsynth(existing) == str(existing)
    assert find_fluidsynth(tmp_path / "missing.exe") is None


def test_find_fluidsynth_reads_env_var_when_not_on_path(monkeypatch, tmp_path) -> None:
    configured = tmp_path / "custom-fluidsynth.exe"
    configured.write_bytes(b"MZ")
    monkeypatch.setenv("SIEGFRIDI_FLUIDSYNTH", str(configured))
    monkeypatch.setattr("siegfridi.synthesis.render.shutil.which", lambda _name: None)

    assert find_fluidsynth() == str(configured)


def test_find_fluidsynth_returns_none_when_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("SIEGFRIDI_FLUIDSYNTH", raising=False)
    monkeypatch.setattr("siegfridi.synthesis.render.shutil.which", lambda _name: None)

    assert find_fluidsynth() is None
