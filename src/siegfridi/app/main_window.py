"""Main Qt workbench for the P2 editor slice."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.editing import CommandStack
from ..core.models import Note, Project, Track
from ..playback import MidiPlayer, open_default_output
from .piano_roll import PianoRollView


def _starter_project() -> Project:
    """Keep the first launch useful without requiring an import wizard."""
    return Project(
        tracks=[
            Track(
                name="Lead",
                role="melody",
                notes=[
                    Note(0, 480, 72, 108),
                    Note(480, 480, 74, 100),
                    Note(960, 960, 76, 106),
                ],
            ),
            Track(name="Gothic Bed", role="pad", notes=[Note(0, 1920, 48, 70)]),
        ],
        style_preset_id="dark-gothic",
    )


class MainWindow(QMainWindow):
    """P2 workbench with track panel, piano roll and basic transport."""

    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"Siegfridi {__version__}")
        self.resize(1200, 760)
        self.project = project or _starter_project()
        self.command_stack = CommandStack()
        self.player = MidiPlayer()

        self.roll = PianoRollView(self.project, self.command_stack)
        self.track_list = QListWidget()
        self.track_list.setMinimumWidth(180)
        self.track_list.currentRowChanged.connect(self.roll.set_track)
        self._populate_tracks()
        self.track_list.setCurrentRow(0)

        self._play_button = QPushButton("Play")
        self._stop_button = QPushButton("Stop")
        self._mute_button = QPushButton("Mute track")
        self._solo_button = QPushButton("Solo track")
        self._play_button.clicked.connect(self._play)
        self._stop_button.clicked.connect(self.player.stop)
        self._mute_button.clicked.connect(self._toggle_mute)
        self._solo_button.clicked.connect(self._toggle_solo)

        toolbar = QToolBar("Edit")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        undo_action = QAction("Undo", self)
        redo_action = QAction("Redo", self)
        undo_action.setShortcut("Ctrl+Z")
        redo_action.setShortcut("Ctrl+Y")
        undo_action.triggered.connect(self.command_stack.undo)
        redo_action.triggered.connect(self.command_stack.redo)
        toolbar.addAction(undo_action)
        toolbar.addAction(redo_action)
        toolbar.addSeparator()
        toolbar.addWidget(self._play_button)
        toolbar.addWidget(self._stop_button)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.addWidget(QLabel("Tracks"))
        panel_layout.addWidget(self.track_list, 1)
        panel_layout.addWidget(self._mute_button)
        panel_layout.addWidget(self._solo_button)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)
        layout.addWidget(self.roll, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready - click the piano roll to add a note")
        self.command_stack.add_listener(self._on_project_changed)

    def _populate_tracks(self) -> None:
        self.track_list.clear()
        for index, track in enumerate(self.project.tracks):
            item = QListWidgetItem(f"{track.name}  [{track.role}]")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.track_list.addItem(item)

    def _on_project_changed(self) -> None:
        self.statusBar().showMessage("Project changed")

    def _play(self) -> None:
        if self.player.output is None:
            output = open_default_output()
            if output is not None:
                self.player.set_output(output)
        self.player.start(self.project)
        message = "Playing" if self.player.output is not None else "Playing (no MIDI output device)"
        self.statusBar().showMessage(message)

    def _current_track(self) -> Track | None:
        row = self.track_list.currentRow()
        return self.project.tracks[row] if 0 <= row < len(self.project.tracks) else None

    def _toggle_mute(self) -> None:
        track = self._current_track()
        if track is None:
            return
        track.muted = not track.muted
        self.statusBar().showMessage(f"{track.name}: {'muted' if track.muted else 'unmuted'}")

    def _toggle_solo(self) -> None:
        track = self._current_track()
        if track is None:
            return
        track.solo = not track.solo
        self.statusBar().showMessage(f"{track.name}: {'solo' if track.solo else 'not solo'}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.player.stop()
        output = self.player.output
        close = getattr(output, "close", None)
        if close is not None:
            close()
        super().closeEvent(event)


def launch() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
