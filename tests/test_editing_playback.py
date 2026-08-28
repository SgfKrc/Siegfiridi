import time

import mido

from siegfridi.core.editing import (
    AddNoteCommand,
    CommandStack,
    find_note_index,
    move_note,
    resize_note,
    set_velocity,
)
from siegfridi.core.models import Note, Project, Track
from siegfridi.playback import MidiPlayer, scheduled_events, tick_to_seconds


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


def test_player_sends_events_without_hardware() -> None:
    project = Project(tracks=[Track(name="Lead", notes=[Note(0, 120, 60)])])
    sent: list[mido.Message] = []
    waits: list[float] = []
    player = MidiPlayer(output=sent.append, sleeper=waits.append)

    player.play_blocking(project)

    assert [message.type for message in sent] == ["note_on", "note_off"]
    assert waits == [0.0, 0.125]


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
