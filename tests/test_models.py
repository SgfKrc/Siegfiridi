from siegfridi.core.models import Note, Project, Track
from siegfridi.midi.files import load_project, save_project
from siegfridi.sound.profiles import SoundProfile, StylePreset


def test_note_quantization_preserves_pitch_and_velocity() -> None:
    note = Note(start_tick=37, duration_tick=205, pitch=60, velocity=91)

    quantized = note.quantized(120)

    assert quantized.start_tick == 0
    assert quantized.end_tick == 240
    assert quantized.pitch == 60
    assert quantized.velocity == 91


def test_project_quantization_preserves_style_and_track_metadata() -> None:
    project = Project(
        tempo_bpm=150,
        style_preset_id="gothic",
        tracks=[
            Track(
                name="Lead",
                role="melody",
                sound_profile_id="organ",
                notes=[Note(start_tick=37, duration_tick=205, pitch=72)],
            )
        ],
    )

    quantized = project.quantized(120)

    assert quantized.style_preset_id == "gothic"
    assert quantized.tempo_bpm == 150
    assert quantized.tracks[0].role == "melody"
    assert quantized.tracks[0].sound_profile_id == "organ"
    assert quantized.tracks[0].notes[0].start_tick == 0


def test_custom_sound_profile_and_style_preset_validate() -> None:
    profile = SoundProfile(
        id="gothic-organ",
        name="Gothic Organ",
        program=19,
        key_switches={"staccato": 36},
    )
    preset = StylePreset(
        id="dark-gothic",
        name="Dark Gothic",
        tempo_min=90,
        tempo_max=170,
        default_roles=("organ", "choir", "bass"),
        sound_profile_ids=(profile.id,),
    )

    assert preset.sound_profile_ids == ("gothic-organ",)


def test_midi_round_trip_preserves_project_boundary(tmp_path) -> None:
    project = Project(
        ppq=960,
        tempo_bpm=137,
        style_preset_id="dark-gothic",
        tracks=[
            Track(
                name="Organ Lead",
                role="melody",
                sound_profile_id="gothic-organ",
                notes=[
                    Note(start_tick=0, duration_tick=480, pitch=72, velocity=110),
                    Note(start_tick=480, duration_tick=240, pitch=74, velocity=96),
                ],
            )
        ],
    )
    path = tmp_path / "round-trip.mid"

    save_project(project, path)
    restored = load_project(path)

    assert restored.ppq == 960
    # Standard MIDI stores tempo as integer microseconds per beat.
    assert abs(restored.tempo_bpm - 137) < 1e-3
    assert restored.tracks[0].name == "Organ Lead"
    assert restored.tracks[0].role == "melody"
    assert restored.tracks[0].sound_profile_id == "gothic-organ"
    assert restored.tracks[0].notes == project.tracks[0].notes
