import json

import pytest

from siegfridi.core import ProjectFileError, load_siegfridi, project_from_dict, save_siegfridi
from siegfridi.core.models import Note, Project, Track


def test_native_project_round_trip_preserves_full_edit_state(tmp_path) -> None:
    project = Project(
        ppq=960,
        tempo_bpm=137.5,
        style_preset_id="dark-gothic",
        sound_pack_id="dark-gothic-v01",
        tracks=[
            Track(
                name="Organ",
                role="melody",
                muted=True,
                solo=False,
                volume=0.65,
                pan=-0.4,
                sound_profile_id="cathedral-organ",
                notes=[Note(120, 480, 72, 111)],
            )
        ],
    )
    path = save_siegfridi(project, tmp_path / "song.siegfridi")

    restored = load_siegfridi(path)

    assert restored.ppq == project.ppq
    assert restored.tempo_bpm == project.tempo_bpm
    assert restored.style_preset_id == project.style_preset_id
    assert restored.sound_pack_id == project.sound_pack_id
    assert restored.tracks[0].volume == project.tracks[0].volume
    assert restored.tracks[0].pan == project.tracks[0].pan
    assert restored.tracks[0].notes == project.tracks[0].notes


def test_native_save_rotates_previous_file_to_backup(tmp_path) -> None:
    project = Project(tracks=[Track("Lead")])
    path = tmp_path / "song.siegfridi"
    save_siegfridi(project, path)
    project.tempo_bpm = 90
    save_siegfridi(project, path)

    assert (tmp_path / "song.siegfridi.bak").is_file()
    assert load_siegfridi(tmp_path / "song.siegfridi.bak").tempo_bpm == 120.0
    assert load_siegfridi(path).tempo_bpm == 90.0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"format": "other", "schema_version": 1}, "unsupported project format"),
        ({"format": "siegfridi-project", "schema_version": 99}, "unsupported project schema"),
        ({"format": "siegfridi-project", "schema_version": 1, "tracks": "bad"}, "tracks"),
    ],
)
def test_native_project_validation_reports_bad_payload(payload, message) -> None:
    with pytest.raises(ProjectFileError, match=message):
        project_from_dict(payload)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"format": "siegfridi-project", "schema_version": 1, "tracks": [{"name": "Lead"}]},
        {"format": "siegfridi-project", "schema_version": 1, "ppq": 480, "tempo_bpm": 120, "tracks": [1]},
        {
            "format": "siegfridi-project",
            "schema_version": 1,
            "ppq": 480,
            "tempo_bpm": 120,
            "tracks": [{"name": "Lead", "notes": [{"start_tick": 0}]}],
        },
    ],
)
def test_native_project_validation_rejects_missing_or_malformed_nested_data(payload) -> None:
    with pytest.raises(ProjectFileError):
        project_from_dict(payload)


def test_native_load_reports_missing_or_invalid_json(tmp_path) -> None:
    with pytest.raises(ProjectFileError, match="could not read"):
        load_siegfridi(tmp_path / "missing.siegfridi")
    invalid = tmp_path / "invalid.siegfridi"
    invalid.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProjectFileError, match="could not read"):
        load_siegfridi(invalid)


def test_native_save_restores_backup_when_atomic_write_fails(monkeypatch, tmp_path) -> None:
    from siegfridi.core import project_io

    path = tmp_path / "recover.siegfridi"
    save_siegfridi(Project(tracks=[Track("Lead")]), path)
    monkeypatch.setattr(project_io, "_atomic_write", lambda *_args: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(OSError, match="disk full"):
        save_siegfridi(Project(tempo_bpm=90, tracks=[Track("Lead")]), path)
    assert load_siegfridi(path).tempo_bpm == 120.0


def test_native_save_requires_project_suffix(tmp_path) -> None:
    with pytest.raises(ProjectFileError, match="suffix"):
        save_siegfridi(Project(), tmp_path / "song.json")


def test_native_file_is_readable_json(tmp_path) -> None:
    path = save_siegfridi(Project(tracks=[Track("Lead")]), tmp_path / "song.siegfridi")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["format"] == "siegfridi-project"
    assert payload["schema_version"] == 1
