import time

import mido
import pytest

from siegfridi.core.editing import (
    AddNoteCommand,
    AddNotesCommand,
    CommandStack,
    find_note_index,
    move_note,
    resize_note,
    set_velocity,
)
from siegfridi.core.models import Note, Project, Track
from siegfridi.playback import (
    MidiPlayer,
    midi_output_names,
    open_default_output,
    scheduled_events,
    tick_to_seconds,
)


def test_edit_commands_round_trip_through_undo_redo() -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 480, 60)])])
    stack = CommandStack()

    added = Note(960, 240, 67, 80)
    stack.execute(AddNoteCommand(project, 0, added))
    stack.execute(move_note(project, 0, 0, 120, 62))
    stack.execute(resize_note(project, 0, 0, 360))
    stack.execute(set_velocity(project, 0, 0, 96))

    assert project.tracks[0].notes[0] == Note(120, 360, 62, 96)
    assert stack.can_undo
    assert stack.undo()
    assert project.tracks[0].notes[0].velocity == 100
    assert stack.undo()
    assert project.tracks[0].notes[0].duration_tick == 480
    assert stack.undo()
    assert project.tracks[0].notes[0].start_tick == 0
    assert stack.undo()
    assert len(project.tracks[0].notes) == 1
    assert stack.can_redo
    assert stack.redo()
    assert len(project.tracks[0].notes) == 2


def test_grouped_note_command_round_trips_as_one_edit() -> None:
    project = Project(tracks=[Track(name="Lead")])
    stack = CommandStack()
    notes = (Note(960, 240, 67, 80), Note(0, 480, 60, 100))

    stack.execute(AddNotesCommand(project, 0, notes))
    assert project.tracks[0].notes == [notes[1], notes[0]]


def test_grouped_note_command_ignores_existing_equal_value_notes_and_undoes_identity() -> None:
    existing = Note(0, 240, 60, 100)
    copied = Note(0, 240, 60, 100)
    project = Project(tracks=[Track(name="Lead", notes=[existing])])
    stack = CommandStack()

    stack.execute(AddNotesCommand(project, 0, (copied,)))
    assert project.tracks[0].notes == [existing, copied]
    assert stack.undo()
    assert project.tracks[0].notes == [existing]


def test_command_stack_empty_operations_and_listener_notifications() -> None:
    project = Project(tracks=[Track(name="Lead")])
    stack = CommandStack()
    notifications = []
    stack.add_listener(lambda: notifications.append(tuple(project.tracks[0].notes)))

    assert stack.undo() is False
    assert stack.redo() is False
    stack.execute(AddNoteCommand(project, 0, Note(0, 120, 60)))
    assert stack.undo()
    assert stack.redo()
    stack.clear()
    assert stack.can_undo is False and stack.can_redo is False
    assert len(notifications) == 3


def test_note_hit_testing_returns_topmost_matching_note() -> None:
    project = Project(
        tracks=[Track(name="Lead", notes=[Note(0, 480, 60), Note(120, 240, 60), Note(0, 240, 64)])]
    )

    assert find_note_index(project, 0, 180, 60) == 1
    assert find_note_index(project, 0, 180, 64) == 2
    assert find_note_index(project, 0, 480, 60) is None


def test_scheduled_events_respect_solo_and_tick_order() -> None:
    project = Project(
        ppq=480,
        tempo_bpm=120,
        tracks=[
            Track(name="Lead", solo=True, notes=[Note(0, 480, 60)]),
            Track(name="Muted", notes=[Note(0, 480, 48)]),
        ],
    )

    events = scheduled_events(project)

    assert [(item.tick, item.message.type, item.message.note) for item in events] == [
        (0, "note_on", 60),
        (480, "note_off", 60),
    ]
    assert tick_to_seconds(480, 480, 120) == 0.5


def test_scheduled_events_reject_negative_start_tick() -> None:
    with pytest.raises(ValueError, match="start_tick"):
        scheduled_events(Project(), start_tick=-1)


def test_player_sends_events_without_hardware() -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 120, 60)])])
    sent: list[mido.Message] = []
    waits: list[float] = []
    player = MidiPlayer(output=sent.append, sleeper=waits.append)

    player.play_blocking(project)

    assert [message.type for message in sent] == ["note_on", "note_off"]
    assert waits == [0.0, 0.125]


def test_midi_output_discovery_and_open_failures_are_safe(monkeypatch) -> None:
    monkeypatch.setattr(mido, "get_output_names", lambda: ["Synth", "External"])
    assert midi_output_names() == ("Synth", "External")

    monkeypatch.setattr(mido, "get_output_names", lambda: (_ for _ in ()).throw(ValueError("backend missing")))
    assert midi_output_names() == ()
    assert open_default_output() is None

    class Output:
        pass

    output = Output()
    monkeypatch.setattr(mido, "open_output", lambda name: output if name == "Synth" else None)
    assert open_default_output("Synth") is output
    monkeypatch.setattr(mido, "open_output", lambda _name: (_ for _ in ()).throw(ValueError("disconnected")))
    assert open_default_output("Synth") is None


def test_player_pause_resume_and_seek_control_background_timeline() -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 240, 60), Note(480, 120, 62)])])
    sent: list[mido.Message] = []
    player = MidiPlayer(output=sent.append)
    player.start(project)
    deadline = time.monotonic() + 1.0
    while not sent and time.monotonic() < deadline:
        time.sleep(0.01)
    player.pause()
    paused_position = player.position_tick
    time.sleep(0.12)
    assert player.is_paused
    assert player.position_tick == paused_position
    player.resume()
    deadline = time.monotonic() + 2.0
    while player.is_playing and time.monotonic() < deadline:
        time.sleep(0.01)
    assert [message.type for message in sent[:2]] == ["note_on", "note_off"]

    player.seek(480)
    assert player.position_tick == 480
    player.start(project, player.position_tick)
    deadline = time.monotonic() + 1.0
    while not any(message.type == "note_on" and message.note == 62 for message in sent) and time.monotonic() < deadline:
        time.sleep(0.01)
    player.stop()
    assert player.is_playing is False
    assert player.position_tick == 0
