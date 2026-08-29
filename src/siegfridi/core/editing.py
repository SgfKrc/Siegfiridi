"""Undoable editing primitives shared by the UI and import post-processing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .models import Note, Project


class EditCommand(Protocol):
    """A reversible mutation of a project."""

    def execute(self) -> None: ...

    def undo(self) -> None: ...


class CommandStack:
    """Small, deterministic undo/redo stack for project edits."""

    def __init__(self) -> None:
        self._undo: list[EditCommand] = []
        self._redo: list[EditCommand] = []
        self._listeners: list[Callable[[], None]] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def add_listener(self, listener: Callable[[], None]) -> None:
        """Call a listener after a command changes the project."""
        self._listeners.append(listener)

    def clear(self) -> None:
        """Discard undo/redo history after replacing the project document."""
        self._undo.clear()
        self._redo.clear()

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def execute(self, command: EditCommand) -> None:
        command.execute()
        self._undo.append(command)
        self._redo.clear()
        self._notify()

    def undo(self) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        self._notify()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.execute()
        self._undo.append(command)
        self._notify()
        return True


def _track(project: Project, track_index: int):
    try:
        return project.tracks[track_index]
    except IndexError as exc:
        raise IndexError(f"track index out of range: {track_index}") from exc


def find_note_index(project: Project, track_index: int, tick: int, pitch: int) -> int | None:
    """Return the topmost note containing a tick/pitch pair."""
    if tick < 0 or not 0 <= pitch <= 127:
        return None
    track = _track(project, track_index)
    for index in range(len(track.notes) - 1, -1, -1):
        note = track.notes[index]
        if note.pitch == pitch and note.start_tick <= tick < note.end_tick:
            return index
    return None


def _replace_note(project: Project, track_index: int, note_index: int, note: Note) -> None:
    track = _track(project, track_index)
    if not 0 <= note_index < len(track.notes):
        raise IndexError(f"note index out of range: {note_index}")
    # Keep the slot stable while a command is being undone/redone. Consumers
    # sort only at presentation/export boundaries, so an index remains valid.
    track.notes[note_index] = note


@dataclass(slots=True)
class AddNoteCommand:
    project: Project
    track_index: int
    note: Note

    def execute(self) -> None:
        track = _track(self.project, self.track_index)
        if self.note not in track.notes:
            track.notes.append(self.note)
            track.notes.sort(key=lambda item: (item.start_tick, item.pitch, item.duration_tick))

    def undo(self) -> None:
        track = _track(self.project, self.track_index)
        track.notes.remove(self.note)


@dataclass(slots=True)
class AddNotesCommand:
    """Add a group of notes as one undoable edit."""

    project: Project
    track_index: int
    notes: tuple[Note, ...]

    def __post_init__(self) -> None:
        self.notes = tuple(self.notes)

    def execute(self) -> None:
        track = _track(self.project, self.track_index)
        for note in self.notes:
            if not any(existing is note for existing in track.notes):
                track.notes.append(note)
        track.notes.sort(key=lambda item: (item.start_tick, item.pitch, item.duration_tick))

    def undo(self) -> None:
        track = _track(self.project, self.track_index)
        track.notes[:] = [
            existing
            for existing in track.notes
            if not any(existing is note for note in self.notes)
        ]


@dataclass(slots=True)
class DeleteNoteCommand:
    project: Project
    track_index: int
    note_index: int
    deleted: Note | None = None

    def execute(self) -> None:
        track = _track(self.project, self.track_index)
        if self.deleted is None:
            self.deleted = track.notes.pop(self.note_index)
        else:
            track.notes.remove(self.deleted)

    def undo(self) -> None:
        if self.deleted is None:
            raise RuntimeError("cannot undo a command that has not executed")
        track = _track(self.project, self.track_index)
        track.notes.insert(min(self.note_index, len(track.notes)), self.deleted)


@dataclass(slots=True)
class ReplaceNoteCommand:
    project: Project
    track_index: int
    note_index: int
    before: Note
    after: Note

    def execute(self) -> None:
        _replace_note(self.project, self.track_index, self.note_index, self.after)

    def undo(self) -> None:
        _replace_note(self.project, self.track_index, self.note_index, self.before)


def move_note(
    project: Project,
    track_index: int,
    note_index: int,
    start_tick: int,
    pitch: int,
) -> ReplaceNoteCommand:
    """Build a command that moves a note while preserving its duration/velocity."""
    current = _track(project, track_index).notes[note_index]
    return ReplaceNoteCommand(
        project,
        track_index,
        note_index,
        current,
        Note(start_tick, current.duration_tick, pitch, current.velocity),
    )


def resize_note(
    project: Project,
    track_index: int,
    note_index: int,
    duration_tick: int,
) -> ReplaceNoteCommand:
    """Build a command that changes a note duration."""
    current = _track(project, track_index).notes[note_index]
    return ReplaceNoteCommand(
        project,
        track_index,
        note_index,
        current,
        Note(current.start_tick, duration_tick, current.pitch, current.velocity),
    )


def set_velocity(
    project: Project,
    track_index: int,
    note_index: int,
    velocity: int,
) -> ReplaceNoteCommand:
    """Build a command that changes note velocity."""
    current = _track(project, track_index).notes[note_index]
    return ReplaceNoteCommand(
        project,
        track_index,
        note_index,
        current,
        Note(current.start_tick, current.duration_tick, current.pitch, velocity),
    )
