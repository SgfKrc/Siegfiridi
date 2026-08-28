"""Main Qt workbench for the development editor slice."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
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
from ..sound import SoundPackError, SoundPackManifest
from ..sound.presets import BUILTIN_STYLE_PRESETS, get_style_preset
from ..synthesis import SynthesisError, render_manifest
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


def _pack_directory() -> Path:
    """Resolve runtime asset packs from a checkout or a frozen bundle."""
    candidates = [Path.cwd() / "assets" / "packs"]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "assets" / "packs")
    candidates.append(Path(__file__).resolve().parents[3] / "assets" / "packs")
    return next((path for path in candidates if path.is_dir()), candidates[0])


def _runtime_pack_paths() -> tuple[Path, ...]:
    """Return only manifests that describe directly loadable SF2/SF3 assets."""
    paths: list[Path] = []
    for path in sorted(_pack_directory().glob("*.json")):
        try:
            manifest = SoundPackManifest.load(path)
        except (OSError, SoundPackError, ValueError, KeyError, TypeError):
            continue
        if Path(manifest.soundfont).suffix.lower() in {".sf2", ".sf3"}:
            paths.append(path)
    return tuple(paths)


class MainWindow(QMainWindow):
    """Development workbench with editing, style, asset and render controls."""

    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"Siegfridi {__version__}")
        self.resize(1200, 760)
        self.project = project or _starter_project()
        self.command_stack = CommandStack()
        self.player = MidiPlayer()

        self.roll = PianoRollView(self.project, self.command_stack)
        self.track_list = QListWidget()
        self.track_list.setMinimumWidth(240)
        self.track_list.currentRowChanged.connect(self.roll.set_track)
        self._populate_tracks()
        self.track_list.setCurrentRow(0)

        self.style_combo = QComboBox()
        for preset in BUILTIN_STYLE_PRESETS:
            self.style_combo.addItem(preset.name, preset.id)
        style_index = max(0, self.style_combo.findData(self.project.style_preset_id))
        self.style_combo.setCurrentIndex(style_index)
        self.style_combo.currentIndexChanged.connect(self._style_changed)

        self.tempo_spin = QDoubleSpinBox()
        self.tempo_spin.setRange(30.0, 300.0)
        self.tempo_spin.setDecimals(1)
        self.tempo_spin.setSingleStep(1.0)
        self.tempo_spin.setValue(self.project.tempo_bpm)
        self.tempo_spin.setSuffix(" BPM")
        self.tempo_spin.valueChanged.connect(self._tempo_changed)

        self.pack_combo = QComboBox()
        self.pack_combo.setToolTip("SoundFont used by offline preview rendering")
        for manifest_path in _runtime_pack_paths():
            manifest = SoundPackManifest.load(manifest_path)
            self.pack_combo.addItem(f"{manifest.name} [{manifest.license}]", str(manifest_path))
        self.pack_combo.currentIndexChanged.connect(self._pack_changed)

        self.render_button = QPushButton("Render preview")
        self.render_button.setToolTip("Render the current project to .siegfridi/preview.wav")
        self.render_button.clicked.connect(self._render_preview)
        if self.pack_combo.count() == 0:
            self.render_button.setEnabled(False)

        self._project_info = QLabel()
        self._project_info.setWordWrap(True)
        self._pack_info = QLabel()
        self._pack_info.setWordWrap(True)
        self._style_info = QLabel()
        self._style_info.setWordWrap(True)
        self._refresh_info()

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
        project_group = QGroupBox("Project")
        project_form = QFormLayout(project_group)
        project_form.addRow("Style", self.style_combo)
        project_form.addRow("Tempo", self.tempo_spin)
        project_form.addRow(self._style_info)
        panel_layout.addWidget(project_group)

        pack_group = QGroupBox("SoundFont")
        pack_form = QFormLayout(pack_group)
        pack_form.addRow("Preview pack", self.pack_combo)
        pack_form.addRow(self._pack_info)
        pack_form.addRow(self.render_button)
        panel_layout.addWidget(pack_group)

        panel_layout.addWidget(QLabel("Tracks"))
        panel_layout.addWidget(self.track_list, 1)
        panel_layout.addWidget(self._mute_button)
        panel_layout.addWidget(self._solo_button)
        panel_layout.addWidget(self._project_info)

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
            states = []
            if track.muted:
                states.append("muted")
            if track.solo:
                states.append("solo")
            suffix = f" ({', '.join(states)})" if states else ""
            item = QListWidgetItem(f"{track.name}  [{track.role}]{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.track_list.addItem(item)

    def _on_project_changed(self) -> None:
        self._refresh_info()
        self.statusBar().showMessage("Project changed")

    def _style_changed(self, _index: int) -> None:
        style_id = self.style_combo.currentData()
        if not isinstance(style_id, str):
            return
        preset = get_style_preset(style_id)
        self.project.style_preset_id = style_id
        self.tempo_spin.setRange(max(30.0, preset.tempo_min), min(300.0, preset.tempo_max))
        self.tempo_spin.setValue(min(max(self.project.tempo_bpm, preset.tempo_min), preset.tempo_max))
        self._refresh_info()
        self.statusBar().showMessage(f"Style: {preset.name}")

    def _tempo_changed(self, value: float) -> None:
        self.project.tempo_bpm = value
        self._refresh_info()

    def _pack_changed(self, _index: int) -> None:
        self._refresh_info()

    def _refresh_info(self) -> None:
        note_count = sum(len(track.notes) for track in self.project.tracks)
        self._project_info.setText(
            f"{len(self.project.tracks)} tracks | {note_count} notes | PPQ {self.project.ppq}"
        )
        style_id = self.style_combo.currentData()
        if isinstance(style_id, str):
            preset = get_style_preset(style_id)
            roles = ", ".join(preset.default_roles)
            self._style_info.setText(f"Roles: {roles}")
        if self.pack_combo.currentIndex() < 0:
            self._pack_info.setText("No runtime SoundFont manifest found")
        else:
            manifest_path = Path(self.pack_combo.currentData())
            manifest = SoundPackManifest.load(manifest_path)
            profiles = ", ".join(profile.id for profile in manifest.profiles[:4])
            self._pack_info.setText(f"v{manifest.version} | profiles: {profiles}")

    def _render_preview(self) -> None:
        manifest_value = self.pack_combo.currentData()
        if not isinstance(manifest_value, str):
            self.statusBar().showMessage("No SoundFont selected")
            return
        output = Path.cwd() / ".siegfridi" / "preview.wav"
        try:
            render_manifest(self.project, manifest_value, output, sample_rate=44100)
        except (OSError, SoundPackError, SynthesisError, ValueError) as exc:
            self.statusBar().showMessage(f"Preview failed: {exc}")
            return
        self.statusBar().showMessage(f"Preview rendered: {output}")

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
        self._populate_tracks()
        self.track_list.setCurrentRow(self.project.tracks.index(track))
        self._refresh_info()
        self.statusBar().showMessage(f"{track.name}: {'muted' if track.muted else 'unmuted'}")

    def _toggle_solo(self) -> None:
        track = self._current_track()
        if track is None:
            return
        track.solo = not track.solo
        self._populate_tracks()
        self.track_list.setCurrentRow(self.project.tracks.index(track))
        self._refresh_info()
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
