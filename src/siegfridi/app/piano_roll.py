"""A compact QGraphicsView piano roll for the P2 editor slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

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
    RULER_HEIGHT = 28.0
    TICK_WIDTH = 0.25
    GRID_TICK = 120
    RULER_TICK = GRID_TICK * 4
    HANDLE_WIDTH = 8.0
    MIN_DURATION_TICK = 30
    LEFT_MARGIN = 48.0
    BLACK_KEY_PITCH_CLASSES = frozenset((1, 3, 6, 8, 10))
    WHITE_KEY_COLOR = QColor("#e6e7eb")
    WHITE_KEY_BORDER = QColor("#9699a3")
    BLACK_KEY_COLOR = QColor("#171922")
    BLACK_KEY_BORDER = QColor("#08090d")
    _THEME_COLORS: ClassVar[dict[str, dict[str, QColor]]] = {
        "dark-gothic": {
            "scene": QColor(23, 23, 29, 224),
            "grid": QColor("#30313b"),
            "beat": QColor("#484957"),
            "bar": QColor("#746076"),
            "ruler": QColor("#292d39"),
            "ruler_text": QColor("#f0dbe5"),
            "cursor": QColor("#f7d06b"),
        },
        "high-contrast": {
            "scene": QColor("#090b0e"),
            "grid": QColor("#202a33"),
            "beat": QColor("#425466"),
            "bar": QColor("#8bd6ff"),
            "ruler": QColor("#18232c"),
            "ruler_text": QColor("#ffffff"),
            "cursor": QColor("#ffe066"),
        },
        "quiet-light": {
            "scene": QColor("#f5f7fa"),
            "grid": QColor("#cfd6df"),
            "beat": QColor("#a5b1bf"),
            "bar": QColor("#66839d"),
            "ruler": QColor("#dce3eb"),
            "ruler_text": QColor("#253342"),
            "cursor": QColor("#c45b23"),
        },
    }

    def __init__(self, project: Project | None = None, command_stack: CommandStack | None = None) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setStyleSheet("background: transparent;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.project = project or Project()
        self.command_stack = command_stack or CommandStack()
        self.track_index = 0
        self.selected_note_index: int | None = None
        self._interaction: _Interaction | None = None
        self._keyboard_keys: dict[int, QGraphicsRectItem] = {}
        self._keyboard_labels: dict[int, QGraphicsSimpleTextItem] = {}
        self._background_pixmap = QPixmap()
        self._background_opacity = 0.18
        self._background_protection = 0.44
        self._background_fit = "cover"
        self._theme_id = "dark-gothic"
        self._playback_tick = 0
        self._playback_cursor: QGraphicsLineItem | None = None
        self._playback_cursor_label: QGraphicsSimpleTextItem | None = None
        self._ruler_labels: dict[int, QGraphicsSimpleTextItem] = {}
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
        return self.RULER_HEIGHT + (127 - pitch) * self.ROW_HEIGHT

    def _y_to_pitch(self, y: float) -> int:
        if y < self.RULER_HEIGHT:
            return 127
        return max(0, min(127, 127 - int((y - self.RULER_HEIGHT) // self.ROW_HEIGHT)))

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

    def set_background_image(
        self,
        path: str | None,
        opacity: float | None = None,
        fit_mode: str | None = None,
        protection: float | None = None,
    ) -> bool:
        """Set the optional image drawn underneath the piano-roll grid."""
        if path is None:
            self._background_pixmap = QPixmap()
            self.refresh()
            return True
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return False
        self._background_pixmap = pixmap
        if opacity is not None:
            self._background_opacity = max(0.0, min(1.0, float(opacity)))
        if fit_mode is not None:
            self._background_fit = fit_mode if fit_mode in {"cover", "fit"} else "cover"
        if protection is not None:
            self._background_protection = max(0.0, min(1.0, float(protection)))
        self.refresh()
        return True

    def set_background_opacity(self, opacity: float) -> None:
        self._background_opacity = max(0.0, min(1.0, float(opacity)))
        self.refresh()

    def set_background_fit(self, fit_mode: str) -> None:
        self._background_fit = fit_mode if fit_mode in {"cover", "fit"} else "cover"
        self.refresh()

    def set_background_protection(self, protection: float) -> None:
        self._background_protection = max(0.0, min(1.0, float(protection)))
        self.refresh()

    def set_theme(self, theme_id: str) -> None:
        self._theme_id = theme_id if theme_id in self._THEME_COLORS else "dark-gothic"
        self.refresh()

    @property
    def playback_tick(self) -> int:
        return self._playback_tick

    def set_playback_tick(self, tick: int) -> None:
        """Move the visible playback cursor without rebuilding note items."""
        self._playback_tick = max(0, int(tick))
        cursor_x = self._tick_to_x(self._playback_tick)
        scene = self.scene()
        if self._playback_cursor is None or cursor_x > scene.sceneRect().right():
            self.refresh()
            return
        self._playback_cursor.setLine(cursor_x, self.RULER_HEIGHT, cursor_x, scene.sceneRect().bottom())
        if self._playback_cursor_label is not None:
            self._playback_cursor_label.setText(str(self._playback_tick))
            self._playback_cursor_label.setPos(cursor_x + 4, self.RULER_HEIGHT - 18)

    @staticmethod
    def _pitch_label(pitch: int) -> str:
        """Return the conventional MIDI note name (MIDI 60 is C4)."""
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        return f"{names[pitch % 12]}{pitch // 12 - 1}"

    def _draw_keyboard(self, scene: QGraphicsScene, height: float) -> None:
        """Paint a read-only 128-key guide into the roll's left margin."""
        self._keyboard_keys = {}
        self._keyboard_labels = {}
        white_pen = QPen(self.WHITE_KEY_BORDER, 0.7)
        black_pen = QPen(self.BLACK_KEY_BORDER, 0.8)

        # White keys form a continuous strip. Black keys are drawn afterwards so
        # their overlap matches a physical piano keyboard.
        for pitch in range(128):
            if pitch % 12 in self.BLACK_KEY_PITCH_CLASSES:
                continue
            key = scene.addRect(0, self._pitch_to_y(pitch), self.LEFT_MARGIN, self.ROW_HEIGHT, white_pen)
            key.setBrush(QBrush(self.WHITE_KEY_COLOR))
            key.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._keyboard_keys[pitch] = key

            if pitch % 12 == 0:
                label = scene.addSimpleText(self._pitch_label(pitch))
                label.setBrush(QBrush(QColor("#252631")))
                label.setPos(3, self._pitch_to_y(pitch) + 1)
                label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                self._keyboard_labels[pitch] = label

        black_width = self.LEFT_MARGIN * 0.62
        black_height = self.ROW_HEIGHT * 0.68
        for pitch in range(128):
            if pitch % 12 not in self.BLACK_KEY_PITCH_CLASSES:
                continue
            key = scene.addRect(
                0,
                self._pitch_to_y(pitch) + (self.ROW_HEIGHT - black_height) / 2,
                black_width,
                black_height,
                black_pen,
            )
            key.setBrush(QBrush(self.BLACK_KEY_COLOR))
            key.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._keyboard_keys[pitch] = key

        separator = scene.addLine(self.LEFT_MARGIN, 0, self.LEFT_MARGIN, height, QPen(QColor("#555866"), 1.2))
        separator.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def refresh(self) -> None:
        scene = self.scene()
        self._playback_cursor = None
        self._playback_cursor_label = None
        self._ruler_labels = {}
        scene.clear()
        colors = self._THEME_COLORS[self._theme_id]
        scene.setBackgroundBrush(QBrush(colors["scene"]))
        max_tick = self.GRID_TICK * 8
        if self.project.tracks:
            track = self.project.tracks[self.track_index]
            max_tick = max(max_tick, max((note.end_tick for note in track.notes), default=0))
        max_tick = max(max_tick, self._playback_tick)
        width = self._tick_to_x(max_tick + self.GRID_TICK)
        height = self.RULER_HEIGHT + 128 * self.ROW_HEIGHT
        scene.setSceneRect(0, 0, width, height)

        if not self._background_pixmap.isNull():
            aspect_mode = (
                Qt.AspectRatioMode.KeepAspectRatio
                if self._background_fit == "fit"
                else Qt.AspectRatioMode.KeepAspectRatioByExpanding
            )
            scaled = self._background_pixmap.scaled(
                int(width), int(height), aspect_mode, Qt.TransformationMode.SmoothTransformation
            )
            image_item = scene.addPixmap(scaled)
            image_item.setOpacity(self._background_opacity)
            image_item.setZValue(-20)
            shade = scene.addRect(0, 0, width, height, QPen(Qt.PenStyle.NoPen))
            shade.setBrush(QBrush(QColor(10, 11, 16, round(self._background_protection * 255))))
            shade.setZValue(-10)

        ruler = scene.addRect(
            self.LEFT_MARGIN,
            0,
            width - self.LEFT_MARGIN,
            self.RULER_HEIGHT,
            QPen(Qt.PenStyle.NoPen),
        )
        ruler.setBrush(QBrush(colors["ruler"]))
        ruler.setZValue(-1)
        ruler.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        dark_pen = QPen(colors["grid"])
        beat_pen = QPen(colors["beat"])
        bar_pen = QPen(colors["bar"], 1.25)
        for pitch in range(128):
            y = self._pitch_to_y(pitch)
            pen = beat_pen if pitch % 12 in (0, 5) else dark_pen
            scene.addLine(self.LEFT_MARGIN, y, width, y, pen)
        for tick in range(0, max_tick + self.GRID_TICK, self.GRID_TICK):
            pen = bar_pen if tick % self.RULER_TICK == 0 else beat_pen
            scene.addLine(self._tick_to_x(tick), 0, self._tick_to_x(tick), height, pen)

        for tick in range(0, max_tick + self.RULER_TICK, self.RULER_TICK):
            label = scene.addSimpleText(str(tick))
            label.setBrush(QBrush(colors["ruler_text"]))
            label.setPos(self._tick_to_x(tick) + 4, 4)
            label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            label.setZValue(2)
            self._ruler_labels[tick] = label

        self._draw_keyboard(scene, height)

        if not self.project.tracks:
            self.selected_note_index = None
        else:
            for index, note in enumerate(self.project.tracks[self.track_index].notes):
                item = PianoRollNoteItem(note, self.track_index, index)
                item.setRect(*self._note_rect(note))
                selected = index == self.selected_note_index
                item.setBrush(QBrush(self._track_color().lighter(145 if selected else 100)))
                item.setPen(QPen(QColor("#fff3f7") if selected else QColor("#111118"), 1.2))
                scene.addItem(item)

        self._playback_cursor = scene.addLine(
            self._tick_to_x(self._playback_tick),
            self.RULER_HEIGHT,
            self._tick_to_x(self._playback_tick),
            height,
            QPen(colors["cursor"], 1.6),
        )
        self._playback_cursor.setZValue(20)
        self._playback_cursor.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._playback_cursor_label = scene.addSimpleText(str(self._playback_tick))
        self._playback_cursor_label.setBrush(QBrush(colors["cursor"]))
        self._playback_cursor_label.setPos(self._tick_to_x(self._playback_tick) + 4, self.RULER_HEIGHT - 18)
        self._playback_cursor_label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._playback_cursor_label.setZValue(21)

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
        if scene_pos.x() < self.LEFT_MARGIN or scene_pos.y() < self.RULER_HEIGHT:
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
