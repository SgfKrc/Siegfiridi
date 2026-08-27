"""A compact QGraphicsView piano roll for the P2 editor slice."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

from ..core.editing import (
    AddNoteCommand,
    CommandStack,
    DeleteNoteCommand,
    move_note,
    resize_note,
)
from ..core.models import Note, Project


@dataclass(slots=True)
class _Interaction:
    kind: str
    track_index: int
    note_index: int
    original: Note
    item: QGraphicsRectItem
    offset_tick: int = 0


class PianoRollNoteItem(QGraphicsRectItem):
    """Graphics item carrying its current note coordinates during a drag."""

    def __init__(self, note: Note, track_index: int, note_index: int) -> None:
        super().__init__()
        self.note = note
        self.track_index = track_index
        self.note_index = note_index
        self.setData(0, track_index)
        self.setData(1, note_index)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


class PianoRollView(QGraphicsView):
    """Viewport-cropped piano roll with basic note editing gestures."""

    ROW_HEIGHT = 14.0
    TICK_WIDTH = 0.25
    GRID_TICK = 120
    HANDLE_WIDTH = 8.0
    MIN_DURATION_TICK = 30
    LEFT_MARGIN = 48.0

    def __init__(self, project: Project | None = None, command_stack: CommandStack | None = None) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.project = project or Project()
        self.command_stack = command_stack or CommandStack()
        self.track_index = 0
        self.selected_note_index: int | None = None
        self._interaction: _Interaction | None = None
        self.command_stack.add_listener(self.refresh)
        self.refresh()

    def set_project(self, project: Project) -> None:
        self.project = project
        self.track_index = min(self.track_index, max(0, len(project.tracks) - 1))
        self.selected_note_index = None
        self.refresh()

    def set_track(self, track_index: int) -> None:
        if not self.project.tracks:
            self.track_index = 0
        elif not 0 <= track_index < len(self.project.tracks):
            raise IndexError(f"track index out of range: {track_index}")
        else:
            self.track_index = track_index
        self.selected_note_index = None
        self.refresh()

    def _tick_to_x(self, tick: int) -> float:
        return self.LEFT_MARGIN + tick * self.TICK_WIDTH

    def _x_to_tick(self, x: float) -> int:
        return max(0, round((x - self.LEFT_MARGIN) / self.TICK_WIDTH))

    def _pitch_to_y(self, pitch: int) -> float:
        return (127 - pitch) * self.ROW_HEIGHT

    def _y_to_pitch(self, y: float) -> int:
        return max(0, min(127, 127 - int(y // self.ROW_HEIGHT)))

    def _snap(self, tick: int) -> int:
        return max(0, round(tick / self.GRID_TICK) * self.GRID_TICK)

    def _note_rect(self, note: Note):
        return (
            self._tick_to_x(note.start_tick),
            self._pitch_to_y(note.pitch) + 1,
            max(3.0, note.duration_tick * self.TICK_WIDTH),
            self.ROW_HEIGHT - 2,
        )

    def _track_color(self) -> QColor:
        colors = ("#d56a8b", "#6ab7d5", "#d5ad6a", "#9e7bd6", "#72c49a")
        return QColor(colors[self.track_index % len(colors)])

    def refresh(self) -> None:
        scene = self.scene()
        scene.clear()
        scene.setBackgroundBrush(QBrush(QColor("#17171d")))
        max_tick = self.GRID_TICK * 8
        if self.project.tracks:
            track = self.project.tracks[self.track_index]
            max_tick = max(max_tick, max((note.end_tick for note in track.notes), default=0))
        width = self._tick_to_x(max_tick + self.GRID_TICK)
        height = 128 * self.ROW_HEIGHT
        scene.setSceneRect(0, 0, width, height)

        dark_pen = QPen(QColor("#25252d"))
        beat_pen = QPen(QColor("#3a3a47"))
        for pitch in range(128):
            y = self._pitch_to_y(pitch)
            pen = beat_pen if pitch % 12 in (0, 5) else dark_pen
            scene.addLine(0, y, width, y, pen)
        for tick in range(0, max_tick + self.GRID_TICK, self.GRID_TICK):
            scene.addLine(self._tick_to_x(tick), 0, self._tick_to_x(tick), height, beat_pen)

        if not self.project.tracks:
            self.selected_note_index = None
            return
        for index, note in enumerate(self.project.tracks[self.track_index].notes):
            item = PianoRollNoteItem(note, self.track_index, index)
            item.setRect(*self._note_rect(note))
            selected = index == self.selected_note_index
            item.setBrush(QBrush(self._track_color().lighter(145 if selected else 100)))
            item.setPen(QPen(QColor("#fff3f7") if selected else QColor("#111118"), 1.2))
            scene.addItem(item)

    def _note_item_at(self, view_pos) -> PianoRollNoteItem | None:
        item = self.itemAt(view_pos)
        return item if isinstance(item, PianoRollNoteItem) else None

    def _update_selection_brushes(self) -> None:
        for graphics_item in self.scene().items():
            if not isinstance(graphics_item, PianoRollNoteItem):
                continue
            selected = graphics_item.note_index == self.selected_note_index
            graphics_item.setBrush(
                QBrush(self._track_color().lighter(145 if selected else 100))
            )
            graphics_item.setPen(
                QPen(QColor("#fff3f7") if selected else QColor("#111118"), 1.2)
            )

    def mousePressEvent(self, event) -> None:
        if not self.project.tracks:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        item = self._note_item_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton:
            if item is not None:
                self.command_stack.execute(
                    DeleteNoteCommand(self.project, self.track_index, item.note_index)
                )
                self.selected_note_index = None
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if item is None:
            tick = self._snap(self._x_to_tick(scene_pos.x()))
            pitch = self._y_to_pitch(scene_pos.y())
            note = Note(tick, self.GRID_TICK * 2, pitch)
            self.command_stack.execute(AddNoteCommand(self.project, self.track_index, note))
            self.selected_note_index = self.project.tracks[self.track_index].notes.index(note)
            self.refresh()
            return
        self.selected_note_index = item.note_index
        self._update_selection_brushes()
        current = self.project.tracks[self.track_index].notes[item.note_index]
        kind = "resize" if scene_pos.x() >= item.sceneBoundingRect().right() - self.HANDLE_WIDTH else "move"
        self._interaction = _Interaction(
            kind,
            self.track_index,
            item.note_index,
            current,
            item,
            self._x_to_tick(scene_pos.x()) - current.start_tick,
        )

    def mouseMoveEvent(self, event) -> None:
        interaction = self._interaction
        if interaction is None:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        note = interaction.original
        if interaction.kind == "move":
            start = self._snap(self._x_to_tick(scene_pos.x()) - interaction.offset_tick)
            pitch = self._y_to_pitch(scene_pos.y())
            current = Note(start, note.duration_tick, pitch, note.velocity)
        else:
            end = self._snap(self._x_to_tick(scene_pos.x()))
            duration = max(self.MIN_DURATION_TICK, end - note.start_tick)
            current = Note(note.start_tick, duration, note.pitch, note.velocity)
        interaction.item.note = current
        interaction.item.setRect(*self._note_rect(current))

    def mouseReleaseEvent(self, event) -> None:
        interaction = self._interaction
        self._interaction = None
        if interaction is None or event.button() != Qt.MouseButton.LeftButton:
            return
        updated = interaction.item.note
        if updated == interaction.original:
            self.refresh()
            return
        if interaction.kind == "move":
            command = move_note(
                self.project,
                interaction.track_index,
                interaction.note_index,
                updated.start_tick,
                updated.pitch,
            )
        else:
            command = resize_note(
                self.project,
                interaction.track_index,
                interaction.note_index,
                updated.duration_tick,
            )
        self.command_stack.execute(command)
        self.selected_note_index = interaction.note_index
        self.refresh()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete and self.selected_note_index is not None:
            self.command_stack.execute(
                DeleteNoteCommand(self.project, self.track_index, self.selected_note_index)
            )
            self.selected_note_index = None
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.command_stack.undo()
                return
            if event.key() == Qt.Key.Key_Y:
                self.command_stack.redo()
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, 1.0)
            event.accept()
            return
        super().wheelEvent(event)
