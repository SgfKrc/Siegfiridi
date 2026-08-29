import pytest

from siegfridi.core.models import Note, Project, Track
from siegfridi.midi.files import load_project, midi_to_project, project_to_midi, save_project
from siegfridi.sound.profiles import SoundProfile, StylePreset


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_tick": -1, "duration_tick": 1, "pitch": 60}, "start_tick"),
        ({"start_tick": 0, "duration_tick": 0, "pitch": 60}, "duration_tick"),
        ({"start_tick": 0, "duration_tick": 1, "pitch": -1}, "pitch"),
        ({"start_tick": 0, "duration_tick": 1, "pitch": 128}, "pitch"),
        ({"start_tick": 0, "duration_tick": 1, "pitch": 60, "velocity": 0}, "velocity"),
        ({"start_tick": 0, "duration_tick": 1, "pitch": 60, "velocity": 128}, "velocity"),
    ],
)
def test_note_rejects_invalid_midi_values(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Note(**kwargs)


def test_note_quantization_requires_positive_grid() -> None:
    with pytest.raises(ValueError, match="grid_tick"):
        Note(0, 1, 60).quantized(0)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Track("", notes=[]),
        lambda: Track("Lead", volume=-0.1),
        lambda: Track("Lead", volume=1.1),
        lambda: Track("Lead", pan=-1.1),
        lambda: Track("Lead", pan=1.1),
        lambda: Project(ppq=0),
        lambda: Project(tempo_bpm=0),
    ],
)
def test_project_and_track_boundaries_are_validated(factory) -> None:
    with pytest.raises(ValueError):
        factory()


def test_sound_profile_and_style_preset_boundaries_are_validated() -> None:
    with pytest.raises(ValueError, match="id"):
        SoundProfile(id="", name="broken")
    with pytest.raises(ValueError, match="bank"):
        SoundProfile(id="lead", name="Lead", bank=16384)
    with pytest.raises(ValueError, match="program"):
        SoundProfile(id="lead", name="Lead", program=128)
    with pytest.raises(ValueError, match="id"):
        StylePreset(id="", name="broken")
    with pytest.raises(ValueError, match="tempo range"):
        StylePreset(id="bad", name="Bad", tempo_min=180, tempo_max=90)


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


def test_midi_export_emits_sound_profile_program_and_bank() -> None:
    project = Project(
        tracks=[Track("Lead", sound_profile_id="brass", notes=[Note(0, 120, 72)])]
    )
    profile = SoundProfile(id="brass", name="Brass", bank=257, program=56)

    midi_track = project_to_midi(project, {profile.id: profile}).tracks[1]
    messages = [message for message in midi_track if not message.is_meta]

    assert [(message.type, getattr(message, "control", None), getattr(message, "value", None)) for message in messages[:2]] == [
        ("control_change", 0, 2),
        ("control_change", 32, 1),
    ]
    assert messages[2].type == "program_change"
    assert messages[2].program == 56


def test_midi_import_handles_velocity_zero_and_unclosed_notes() -> None:
    import mido

    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    track.extend(
        [
            mido.MetaMessage("track_name", name="Input"),
            mido.Message("note_on", note=60, velocity=90, time=0),
            mido.Message("note_on", note=60, velocity=0, time=120),
            mido.Message("note_on", note=64, velocity=80, time=120),
            mido.MetaMessage("end_of_track", time=240),
        ]
    )
    midi.tracks.append(track)

    project = midi_to_project(midi)

    assert project.tracks[0].notes == [Note(0, 120, 60, 90), Note(240, 240, 64, 80)]


def test_midi_import_pairs_overlapping_same_pitch_notes_fifo() -> None:
    import mido

    midi = mido.MidiFile(ticks_per_beat=480)
    midi.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("note_on", note=60, velocity=70, time=0),
                mido.Message("note_on", note=60, velocity=90, time=120),
                mido.Message("note_off", note=60, velocity=0, time=120),
                mido.Message("note_off", note=60, velocity=0, time=120),
            ]
        )
    )

    project = midi_to_project(midi)

    assert project.tracks[0].notes == [Note(0, 240, 60, 70), Note(120, 240, 60, 90)]


def test_midi_export_orders_note_off_before_note_on_at_same_tick() -> None:
    project = Project(
        tracks=[
            Track(
                "Lead",
                notes=[Note(0, 480, 60), Note(480, 240, 64)],
            )
        ]
    )

    messages = [message for message in project_to_midi(project).tracks[1] if not message.is_meta]

    assert [(message.type, message.time) for message in messages] == [
        ("note_on", 0),
        ("note_off", 480),
        ("note_on", 0),
        ("note_off", 240),
    ]


def test_midi_round_trip_preserves_track_mix_controls(tmp_path) -> None:
    project = Project(
        tracks=[
            Track("Mix", volume=0.5, pan=-0.5, notes=[Note(0, 120, 60)]),
        ]
    )

    path = tmp_path / "mix.mid"
    save_project(project, path)
    restored = load_project(path)

    assert abs(restored.tracks[0].volume - (round(0.5 * 127) / 127.0)) < 1e-9
    assert abs(restored.tracks[0].pan - (round(0.5 * 63.5) / 63.5 - 1.0)) < 1e-9
