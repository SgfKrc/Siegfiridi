"""Main Qt workbench for the development editor slice."""

from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.editing import AddNoteCommand, CommandStack
from ..core.models import Note, Project, Track
from ..core.project_io import ProjectFileError, autosave_project, load_siegfridi, save_siegfridi
from ..midi import (
    MidiKeyboardEvent,
    MidiKeyboardInput,
    MidiKeyboardMapping,
    midi_input_names,
    open_midi_input,
)
from ..playback import MidiPlayer, open_default_output
from ..sound import SoundPackError, SoundPackManifest
from ..sound.presets import BUILTIN_STYLE_PRESETS, get_style_preset
from ..synthesis import SynthesisError, render_manifest
from ..transcription import TranscriptionResult, append_result_track, summarize_candidates
from ..workers.transcription import TranscriptionProcess, TranscriptionRequest
from .piano_roll import PianoRollView

_WORKBENCH_STYLE = """
QMainWindow { background: #11131a; }
QToolBar {
    background: #20232c;
    border: 0;
    border-bottom: 1px solid #3a3f4c;
    spacing: 6px;
    padding: 5px 7px;
}
QToolButton {
    color: #ececf2;
    padding: 5px 9px;
    border-radius: 4px;
}
QToolButton:hover { background: #363b49; }
QWidget#controlPanel {
    background: rgba(25, 28, 36, 224);
    border-right: 1px solid #3a3f4c;
}
QGroupBox {
    color: #f0e8ee;
    background: rgba(28, 31, 40, 232);
    border: 1px solid #414653;
    border-radius: 6px;
    margin-top: 10px;
    padding: 12px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 4px;
}
QLabel { color: #c9cbd4; }
QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {
    background: #20242e;
    color: #f0f1f5;
    border: 1px solid #4b5160;
    border-radius: 4px;
    padding: 3px 5px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QListWidget:hover {
    border-color: #b86a8e;
}
QListWidget { selection-background-color: #9d5277; }
QPushButton {
    background: #363b49;
    color: #f1edf1;
    border: 1px solid #515868;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover { background: #4a4051; border-color: #c06b94; }
QPushButton:pressed { background: #2e3240; }
QPushButton:disabled { color: #777b86; background: #292d37; }
QStatusBar { background: #20232c; color: #c9cbd4; }
QScrollArea#controlScroll { background: transparent; border: 0; }
"""

_THEME_PRESETS = (
    ("dark-gothic", "Dark Gothic"),
    ("high-contrast", "High Contrast"),
    ("quiet-light", "Quiet Light"),
)
_THEME_OVERRIDES = {
    "dark-gothic": "",
    "high-contrast": """
QMainWindow { background: #090b0e; }
QToolBar, QStatusBar { background: #11151a; }
QWidget#controlPanel, QGroupBox { background: rgba(12, 16, 20, 242); }
QComboBox, QSpinBox, QDoubleSpinBox, QListWidget { background: #10151a; color: #ffffff; border-color: #8c9aa8; }
QPushButton { background: #1b242d; color: #ffffff; border-color: #a9bac8; }
QPushButton:hover { background: #2c3a46; border-color: #ffffff; }
QListWidget { selection-background-color: #006f9f; }
QLabel, QGroupBox { color: #ffffff; }
""",
    "quiet-light": """
QMainWindow { background: #e9edf2; }
QToolBar, QStatusBar { background: #d7dde5; }
QToolButton, QStatusBar { color: #202631; }
QWidget#controlPanel, QGroupBox { background: rgba(245, 247, 250, 242); }
QGroupBox { color: #202631; border-color: #aab4c1; }
QLabel { color: #303844; }
QComboBox, QSpinBox, QDoubleSpinBox, QListWidget { background: #ffffff; color: #202631; border-color: #8d99a8; }
QPushButton { background: #e2e7ed; color: #202631; border-color: #8d99a8; }
QPushButton:hover { background: #d4dce5; border-color: #536779; }
QListWidget { selection-background-color: #8fb5cc; }
""",
}


def _theme_style(theme_id: str) -> str:
    """Return a complete stylesheet while keeping the original dark theme stable."""
    return _WORKBENCH_STYLE + _THEME_OVERRIDES.get(theme_id, _THEME_OVERRIDES["dark-gothic"])


class _BackdropWidget(QWidget):
    """Paint a dimmable, mouse-transparent image behind the workbench."""

    def __init__(self) -> None:
        super().__init__()
        self._pixmap = QPixmap()
        self._opacity = 0.18
        self._protection = 0.44
        self._fit_mode = "cover"
        self._theme_id = "dark-gothic"

    def set_image(self, path: str | Path | None) -> bool:
        if path is None:
            self._pixmap = QPixmap()
            self.update()
            return True
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        self._pixmap = pixmap
        self.update()
        return True

    def set_opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def set_protection(self, value: float) -> None:
        self._protection = max(0.0, min(1.0, float(value)))
        self.update()

    def set_fit_mode(self, mode: str) -> None:
        self._fit_mode = mode if mode in {"cover", "fit"} else "cover"
        self.update()

    def set_theme(self, theme_id: str) -> None:
        self._theme_id = theme_id if theme_id in {item[0] for item in _THEME_PRESETS} else "dark-gothic"
        self.update()

    @property
    def opacity(self) -> float:
        return self._opacity

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        base_color = {
            "dark-gothic": QColor("#11131a"),
            "high-contrast": QColor("#090b0e"),
            "quiet-light": QColor("#e9edf2"),
        }[self._theme_id]
        painter.fillRect(self.rect(), base_color)
        if self._pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        aspect_mode = (
            Qt.AspectRatioMode.KeepAspectRatio
            if self._fit_mode == "fit"
            else Qt.AspectRatioMode.KeepAspectRatioByExpanding
        )
        scaled = self._pixmap.scaled(self.size(), aspect_mode, Qt.TransformationMode.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.setOpacity(self._opacity)
        painter.drawPixmap(x, y, scaled)
        painter.setOpacity(1.0)
        # Preserve text and note contrast even when a bright image is selected.
        painter.fillRect(self.rect(), QColor(10, 11, 16, round(self._protection * 255)))


class _MidiEventBridge(QObject):
    event_received = Signal(object)


def _starter_project() -> Project:
    """Keep the first launch useful without requiring an import wizard."""
    return Project(
        tracks=[
            Track(
                name="Lead",
                role="melody",
                sound_profile_id="cathedral-organ",
                notes=[
                    Note(0, 480, 72, 108),
                    Note(480, 480, 74, 100),
                    Note(960, 960, 76, 106),
                ],
            ),
            Track(
                name="Gothic Bed",
                role="pad",
                sound_profile_id="bowed-bass",
                notes=[Note(0, 1920, 48, 70)],
            ),
        ],
        style_preset_id="dark-gothic",
        sound_pack_id="dark-gothic-v01",
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
        self._settings = QSettings("Siegfridi", "Siegfridi")
        self._theme_id = self._read_theme_id()
        self.setStyleSheet(_theme_style(self._theme_id))
        self.setWindowTitle(f"Siegfridi {__version__}")
        self.resize(1200, 760)
        self.project = project or _starter_project()
        self.project_path: Path | None = None
        self._dirty = False
        self._ready = False
        self.command_stack = CommandStack()
        self.player = MidiPlayer()
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(50)
        self._playback_timer.timeout.connect(self._sync_playback_cursor)
        self._transcription_timer = QTimer(self)
        self._transcription_timer.setInterval(50)
        self._transcription_timer.timeout.connect(self._poll_transcription)
        self._transcription_process: TranscriptionProcess | None = None
        self._pending_transcription: TranscriptionResult | None = None
        self._background_path: Path | None = None
        self._background_opacity = self._read_background_opacity()
        self._background_fit = self._read_background_fit()
        self._background_protection = self._read_background_protection()
        self._midi_mapping = self._read_midi_mapping()
        self._midi_input: MidiKeyboardInput | None = None
        self._midi_bridge = _MidiEventBridge(self)
        self._midi_bridge.event_received.connect(self._on_midi_event)
        self._midi_output_notes: set[tuple[int, int]] = set()
        self._midi_record_active: dict[tuple[int, int], tuple[int, int]] = {}
        self._midi_record_anchor_tick = 0
        self._midi_record_anchor_time = monotonic()

        self.roll = PianoRollView(self.project, self.command_stack)
        self.roll.set_theme(self._theme_id)
        self.track_list = QListWidget()
        self.track_list.setMinimumWidth(240)
        self.track_list.currentRowChanged.connect(self._on_track_changed)
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

        self._position_slider = QSlider(Qt.Orientation.Horizontal)
        self._position_slider.setToolTip("Playback position in project ticks")
        self._position_slider.valueChanged.connect(self._seek_changed)

        self._volume_spin = QDoubleSpinBox()
        self._volume_spin.setRange(0.0, 1.0)
        self._volume_spin.setDecimals(2)
        self._volume_spin.setSingleStep(0.05)
        self._volume_spin.valueChanged.connect(self._volume_changed)
        self._pan_spin = QDoubleSpinBox()
        self._pan_spin.setRange(-1.0, 1.0)
        self._pan_spin.setDecimals(2)
        self._pan_spin.setSingleStep(0.05)
        self._pan_spin.valueChanged.connect(self._pan_changed)

        self._confidence_spin = QDoubleSpinBox()
        self._confidence_spin.setRange(0.0, 1.0)
        self._confidence_spin.setDecimals(2)
        self._confidence_spin.setSingleStep(0.05)
        self._confidence_spin.setValue(0.5)
        self._confidence_spin.setToolTip("Minimum confidence for accepted candidate notes")
        self._confidence_spin.valueChanged.connect(self._refresh_candidate_info)
        self._quantize_spin = QSpinBox()
        self._quantize_spin.setRange(0, 3840)
        self._quantize_spin.setSingleStep(30)
        self._quantize_spin.setValue(120)
        self._quantize_spin.setSuffix(" ticks")
        self._quantize_spin.setToolTip("Grid used when accepting candidate notes; zero disables quantization")
        self._candidate_info = QLabel("No transcription result")
        self._candidate_info.setWordWrap(True)

        self.pack_combo = QComboBox()
        self.pack_combo.setToolTip("SoundFont used by offline preview rendering")
        for manifest_path in _runtime_pack_paths():
            manifest = SoundPackManifest.load(manifest_path)
            self.pack_combo.addItem(f"{manifest.name} [{manifest.license}]", str(manifest_path))
        self.pack_combo.currentIndexChanged.connect(self._pack_changed)
        self._select_project_pack()

        self.render_button = QPushButton("Render preview")
        self.render_button.setToolTip("Render the current project to .siegfridi/preview.wav")
        self.render_button.setStatusTip("Render the current project to a WAV preview")
        self.render_button.clicked.connect(self._render_preview)
        if self.pack_combo.count() == 0:
            self.render_button.setEnabled(False)

        self._import_button = QPushButton("Import audio")
        self._import_button.setToolTip("Run Basic Pitch and prepare candidate notes")
        self._import_button.setStatusTip("Run Basic Pitch and prepare candidate notes")
        self._import_button.clicked.connect(self.import_audio)
        self._cancel_import_button = QPushButton("Cancel import")
        self._cancel_import_button.setEnabled(False)
        self._cancel_import_button.setToolTip("Cancel the running transcription without changing the project")
        self._cancel_import_button.setStatusTip("Cancel the running transcription")
        self._cancel_import_button.clicked.connect(self.cancel_transcription)
        self._accept_button = QPushButton("Accept candidates")
        self._accept_button.setEnabled(False)
        self._accept_button.setToolTip("Add the reviewed transcription candidates to a new track")
        self._accept_button.setStatusTip("Add reviewed transcription candidates to the project")
        self._accept_button.clicked.connect(self.accept_transcription)

        self._project_info = QLabel()
        self._project_info.setWordWrap(True)
        self._pack_info = QLabel()
        self._pack_info.setWordWrap(True)
        self._style_info = QLabel()
        self._style_info.setWordWrap(True)
        self._theme_combo = QComboBox()
        for theme_id, theme_name in _THEME_PRESETS:
            self._theme_combo.addItem(theme_name, theme_id)
        self._theme_combo.setCurrentIndex(max(0, self._theme_combo.findData(self._theme_id)))
        self._theme_combo.currentIndexChanged.connect(self._theme_changed)
        self._background_button = QPushButton("Choose image")
        self._background_button.setToolTip("Choose a local image for the workbench background")
        self._background_button.clicked.connect(self._choose_background)
        self._background_clear_button = QPushButton("Clear")
        self._background_clear_button.setToolTip("Remove the custom workbench background")
        self._background_clear_button.clicked.connect(self._clear_background)
        background_actions = QHBoxLayout()
        background_actions.setContentsMargins(0, 0, 0, 0)
        background_actions.addWidget(self._background_button)
        background_actions.addWidget(self._background_clear_button)
        self._background_opacity_spin = QDoubleSpinBox()
        self._background_opacity_spin.setRange(0.0, 1.0)
        self._background_opacity_spin.setDecimals(2)
        self._background_opacity_spin.setSingleStep(0.05)
        self._background_opacity_spin.setSuffix(" opacity")
        self._background_opacity_spin.setValue(self._background_opacity)
        self._background_opacity_spin.setToolTip("Background image opacity; lower values keep notes easier to read")
        self._background_opacity_spin.valueChanged.connect(self._background_opacity_changed)
        self._background_fit_combo = QComboBox()
        self._background_fit_combo.addItem("Cover", "cover")
        self._background_fit_combo.addItem("Fit", "fit")
        self._background_fit_combo.setCurrentIndex(max(0, self._background_fit_combo.findData(self._background_fit)))
        self._background_fit_combo.setToolTip("Cover crops to fill the workspace; Fit keeps the whole image visible")
        self._background_fit_combo.currentIndexChanged.connect(self._background_fit_changed)
        self._background_protection_spin = QDoubleSpinBox()
        self._background_protection_spin.setRange(0.0, 1.0)
        self._background_protection_spin.setDecimals(2)
        self._background_protection_spin.setSingleStep(0.05)
        self._background_protection_spin.setSuffix(" protection")
        self._background_protection_spin.setValue(self._background_protection)
        self._background_protection_spin.setToolTip("Dark overlay strength used to keep notes readable")
        self._background_protection_spin.valueChanged.connect(self._background_protection_changed)
        self._appearance_reset_button = QPushButton("Restore defaults")
        self._appearance_reset_button.setToolTip("Restore the default theme and background settings")
        self._appearance_reset_button.clicked.connect(self._reset_appearance)
        self._background_info = QLabel("No background image")
        self._background_info.setWordWrap(True)

        self._midi_input_combo = QComboBox()
        self._midi_input_combo.addItem("No MIDI input", None)
        self._midi_input_combo.setToolTip("Choose a connected MIDI keyboard or controller")
        self._midi_input_combo.currentIndexChanged.connect(self._midi_input_changed)
        self._midi_refresh_button = QPushButton("Refresh")
        self._midi_refresh_button.setToolTip("Re-scan MIDI input devices")
        self._midi_refresh_button.clicked.connect(self._refresh_midi_inputs)
        midi_refresh_actions = QHBoxLayout()
        midi_refresh_actions.setContentsMargins(0, 0, 0, 0)
        midi_refresh_actions.addWidget(self._midi_input_combo, 1)
        midi_refresh_actions.addWidget(self._midi_refresh_button)
        self._midi_lowest_spin = QSpinBox()
        self._midi_lowest_spin.setRange(0, 127)
        self._midi_lowest_spin.setValue(self._midi_mapping.lowest_note)
        self._midi_lowest_spin.setToolTip("Lowest note sent by the controller, 0-127")
        self._midi_key_count_spin = QSpinBox()
        self._midi_key_count_spin.setRange(1, 128 - self._midi_mapping.lowest_note)
        self._midi_key_count_spin.setValue(self._midi_mapping.key_count)
        self._midi_key_count_spin.setToolTip("Physical key count, for example 25, 49, 61, 76 or 88")
        self._midi_target_spin = QSpinBox()
        self._midi_target_spin.setRange(0, 128 - self._midi_mapping.key_count)
        self._midi_target_spin.setValue(self._midi_mapping.target_lowest_note)
        self._midi_target_spin.setToolTip("Target pitch for the controller's lowest key")
        self._midi_lowest_spin.valueChanged.connect(self._midi_mapping_changed)
        self._midi_key_count_spin.valueChanged.connect(self._midi_mapping_changed)
        self._midi_target_spin.valueChanged.connect(self._midi_mapping_changed)
        self._midi_thru_check = QCheckBox("MIDI Thru")
        self._midi_thru_check.setChecked(True)
        self._midi_thru_check.setToolTip("Send incoming keyboard notes to the selected MIDI output")
        self._midi_record_check = QCheckBox("Record into selected track")
        self._midi_record_check.setToolTip("Write incoming notes into the selected track using the position cursor")
        self._midi_record_check.toggled.connect(self._midi_record_toggled)
        self._midi_info = QLabel("No MIDI input selected")
        self._midi_info.setWordWrap(True)
        self._refresh_info()

        self._play_button = QPushButton("Play")
        self._play_button.setToolTip("Start playback from the current position")
        self._play_button.setStatusTip("Start playback from the current position")
        self._pause_button = QPushButton("Pause")
        self._pause_button.setToolTip("Pause or resume playback")
        self._pause_button.setStatusTip("Pause or resume playback")
        self._stop_button = QPushButton("Stop")
        self._stop_button.setToolTip("Stop playback and reset the position")
        self._stop_button.setStatusTip("Stop playback and reset the position")
        self._mute_button = QPushButton("Mute track")
        self._mute_button.setToolTip("Toggle mute for the selected track")
        self._mute_button.setStatusTip("Toggle mute for the selected track")
        self._solo_button = QPushButton("Solo track")
        self._solo_button.setToolTip("Toggle solo for the selected track")
        self._solo_button.setStatusTip("Toggle solo for the selected track")
        self._play_button.clicked.connect(self._play)
        self._pause_button.clicked.connect(self._toggle_pause)
        self._stop_button.clicked.connect(self._stop_playback)
        self._mute_button.clicked.connect(self._toggle_mute)
        self._solo_button.clicked.connect(self._toggle_solo)

        toolbar = QToolBar("Edit")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self._new_action = QAction("New", self)
        self._new_action.setToolTip("Create a new project")
        self._new_action.setStatusTip("Create a new project")
        self._new_action.triggered.connect(lambda: self.new_project())
        self._open_action = QAction("Open", self)
        self._open_action.setShortcut("Ctrl+O")
        self._open_action.setToolTip("Open a Siegfridi project (Ctrl+O)")
        self._open_action.setStatusTip("Open a Siegfridi project")
        self._open_action.triggered.connect(self.open_project)
        self._save_action = QAction("Save", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.setToolTip("Save the current project (Ctrl+S)")
        self._save_action.setStatusTip("Save the current project")
        self._save_action.triggered.connect(self.save_project)
        toolbar.addAction(self._new_action)
        toolbar.addAction(self._open_action)
        toolbar.addAction(self._save_action)
        toolbar.addSeparator()
        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.setToolTip("Undo the last edit (Ctrl+Z)")
        self._undo_action.setStatusTip("Undo the last edit")
        self._undo_action.triggered.connect(self.command_stack.undo)
        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut("Ctrl+Y")
        self._redo_action.setToolTip("Redo the last undone edit (Ctrl+Y)")
        self._redo_action.setStatusTip("Redo the last undone edit")
        self._redo_action.triggered.connect(self.command_stack.redo)
        toolbar.addAction(self._undo_action)
        toolbar.addAction(self._redo_action)
        toolbar.addSeparator()
        toolbar.addWidget(self._play_button)
        toolbar.addWidget(self._pause_button)
        toolbar.addWidget(self._stop_button)

        panel = QWidget()
        panel.setObjectName("controlPanel")
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(460)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        project_group = QGroupBox("Project")
        project_form = QFormLayout(project_group)
        project_form.addRow("Style", self.style_combo)
        project_form.addRow("Tempo", self.tempo_spin)
        project_form.addRow("Position", self._position_slider)
        project_form.addRow(self._style_info)
        panel_layout.addWidget(project_group)

        appearance_group = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_group)
        appearance_form.addRow("Theme", self._theme_combo)
        appearance_form.addRow("Background", background_actions)
        appearance_form.addRow("Image opacity", self._background_opacity_spin)
        appearance_form.addRow("Image fit", self._background_fit_combo)
        appearance_form.addRow("Protection", self._background_protection_spin)
        appearance_form.addRow(self._background_info)
        appearance_form.addRow(self._appearance_reset_button)
        panel_layout.addWidget(appearance_group)

        midi_group = QGroupBox("MIDI Keyboard")
        midi_form = QFormLayout(midi_group)
        midi_form.addRow("Input", midi_refresh_actions)
        midi_form.addRow("Lowest note", self._midi_lowest_spin)
        midi_form.addRow("Key count", self._midi_key_count_spin)
        midi_form.addRow("Target lowest", self._midi_target_spin)
        midi_form.addRow(self._midi_thru_check)
        midi_form.addRow(self._midi_record_check)
        midi_form.addRow(self._midi_info)
        panel_layout.addWidget(midi_group)

        pack_group = QGroupBox("SoundFont")
        pack_form = QFormLayout(pack_group)
        pack_form.addRow("Preview pack", self.pack_combo)
        pack_form.addRow(self._pack_info)
        pack_form.addRow(self.render_button)
        pack_form.addRow(self._import_button)
        pack_form.addRow(self._cancel_import_button)
        pack_form.addRow("Confidence", self._confidence_spin)
        pack_form.addRow("Quantize", self._quantize_spin)
        pack_form.addRow(self._candidate_info)
        pack_form.addRow(self._accept_button)
        panel_layout.addWidget(pack_group)

        panel_layout.addWidget(QLabel("Tracks"))
        panel_layout.addWidget(self.track_list, 1)
        track_mix_form = QFormLayout()
        track_mix_form.addRow("Volume", self._volume_spin)
        track_mix_form.addRow("Pan", self._pan_spin)
        panel_layout.addLayout(track_mix_form)
        panel_layout.addWidget(self._mute_button)
        panel_layout.addWidget(self._solo_button)
        panel_layout.addWidget(self._project_info)

        control_scroll = QScrollArea()
        control_scroll.setObjectName("controlScroll")
        control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        control_scroll.setWidgetResizable(True)
        control_scroll.setMinimumWidth(360)
        control_scroll.setMaximumWidth(460)
        control_scroll.setWidget(panel)
        self._control_scroll = control_scroll

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(control_scroll)
        layout.addWidget(self.roll, 1)
        self._backdrop = _BackdropWidget()
        backdrop_layout = QHBoxLayout(self._backdrop)
        backdrop_layout.setContentsMargins(0, 0, 0, 0)
        backdrop_layout.addWidget(workspace)
        self.setCentralWidget(self._backdrop)
        self._load_background_preferences()
        self._refresh_midi_inputs()
        self.statusBar().showMessage("Ready - click the piano roll to add a note")
        self.command_stack.add_listener(self._on_project_changed)
        self._ready = True
        self._update_position_range()
        self._sync_track_controls()
        self._update_window_title()

    def _populate_tracks(self) -> None:
        signals_blocked = self.track_list.blockSignals(True)
        try:
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
        finally:
            self.track_list.blockSignals(signals_blocked)

    def _on_track_changed(self, index: int) -> None:
        """Ignore the transient -1 emitted while Qt clears a list widget."""
        if index >= 0:
            self.roll.set_track(index)
        self._sync_track_controls()

    def _on_project_changed(self) -> None:
        self._dirty = True
        self._autosave()
        self._update_position_range()
        self._refresh_info()
        self._update_window_title()
        self.statusBar().showMessage("Project changed")

    def _autosave(self) -> None:
        if not self._ready:
            return
        try:
            autosave_project(self.project, Path.cwd() / ".siegfridi")
        except (OSError, ProjectFileError) as exc:
            self.statusBar().showMessage(f"Autosave failed: {exc}")

    def _update_window_title(self) -> None:
        marker = " *" if self._dirty else ""
        self.setWindowTitle(f"Siegfridi {__version__}{marker}")

    @staticmethod
    def _setting_value(settings: QSettings, key: str, default, *compatibility_keys: str):
        """Read a namespaced preference while accepting keys from early builds."""
        for candidate in (key, *compatibility_keys):
            if settings.contains(candidate):
                return settings.value(candidate)
        return default

    @staticmethod
    def _unit_value(value, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, parsed)) if math.isfinite(parsed) else default

    def _read_theme_id(self) -> str:
        value = self._setting_value(self._settings, "appearance/theme", "dark-gothic", "theme")
        return value if isinstance(value, str) and value in dict(_THEME_PRESETS) else "dark-gothic"

    def _read_background_opacity(self) -> float:
        raw_value = self._setting_value(
            self._settings,
            "appearance/background_opacity",
            0.18,
            "background_opacity",
        )
        return self._unit_value(raw_value, 0.18)

    def _read_background_fit(self) -> str:
        value = self._setting_value(self._settings, "appearance/background_fit", "cover", "background_fit")
        return value if isinstance(value, str) and value in {"cover", "fit"} else "cover"

    def _read_background_protection(self) -> float:
        value = self._setting_value(
            self._settings,
            "appearance/background_protection",
            0.44,
            "background_protection",
        )
        return self._unit_value(value, 0.44)

    def _load_background_preferences(self) -> None:
        self._backdrop.set_theme(self._theme_id)
        self._backdrop.set_opacity(self._background_opacity)
        self._backdrop.set_fit_mode(self._background_fit)
        self._backdrop.set_protection(self._background_protection)
        self.roll.set_background_fit(self._background_fit)
        self.roll.set_background_protection(self._background_protection)
        raw_path = self._setting_value(self._settings, "appearance/background_path", "", "background_path")
        if isinstance(raw_path, str) and raw_path:
            candidate = Path(raw_path).expanduser()
            if candidate.is_file() and self._backdrop.set_image(candidate):
                self._background_path = candidate
                self.roll.set_background_image(
                    str(candidate),
                    self._background_opacity,
                    self._background_fit,
                    self._background_protection,
                )
            else:
                self._settings.remove("appearance/background_path")
        self._refresh_background_info()

    def _refresh_background_info(self) -> None:
        if self._background_path is None:
            self._background_info.setText("No background image")
            self._background_info.setToolTip("")
        else:
            self._background_info.setText(
                f"{self._background_path.name} | {self._background_opacity_spin.value():.0%}"
            )
            self._background_info.setToolTip(str(self._background_path))
        self._background_clear_button.setEnabled(self._background_path is not None)

    def set_background_image(self, path: str | Path | None, *, persist: bool = True) -> bool:
        """Set or clear the user-level workbench background image."""
        if path is None:
            self._background_path = None
            self._backdrop.set_image(None)
            self.roll.set_background_image(None)
            if persist:
                self._settings.remove("appearance/background_path")
            self._refresh_background_info()
            return True
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_file() or not self._backdrop.set_image(candidate):
            self.statusBar().showMessage(f"Background failed to load: {candidate}")
            return False
        if not self.roll.set_background_image(
            str(candidate),
            self._background_opacity,
            self._background_fit,
            self._background_protection,
        ):
            self.statusBar().showMessage(f"Background failed to load: {candidate}")
            return False
        self._background_path = candidate
        if persist:
            self._settings.setValue("appearance/background_path", str(candidate))
        self._refresh_background_info()
        self.statusBar().showMessage(f"Background: {candidate.name}")
        return True

    def set_background_opacity(self, value: float, *, persist: bool = True) -> None:
        """Set image opacity through the same bounded control used by the UI."""
        clamped = self._unit_value(value, 0.18)
        blocked = self._background_opacity_spin.blockSignals(True)
        try:
            self._background_opacity_spin.setValue(clamped)
        finally:
            self._background_opacity_spin.blockSignals(blocked)
        self._background_opacity = clamped
        self._backdrop.set_opacity(clamped)
        self.roll.set_background_opacity(clamped)
        if persist:
            self._settings.setValue("appearance/background_opacity", clamped)
        self._refresh_background_info()

    def set_background_fit(self, fit_mode: str, *, persist: bool = True) -> None:
        """Choose whether a background covers the workspace or remains fully visible."""
        mode = fit_mode if fit_mode in {"cover", "fit"} else "cover"
        blocked = self._background_fit_combo.blockSignals(True)
        try:
            self._background_fit_combo.setCurrentIndex(max(0, self._background_fit_combo.findData(mode)))
        finally:
            self._background_fit_combo.blockSignals(blocked)
        self._background_fit = mode
        self._backdrop.set_fit_mode(mode)
        self.roll.set_background_fit(mode)
        if persist:
            self._settings.setValue("appearance/background_fit", mode)
        self._refresh_background_info()

    def set_background_protection(self, value: float, *, persist: bool = True) -> None:
        """Set the readability overlay strength independently from image opacity."""
        clamped = self._unit_value(value, 0.44)
        blocked = self._background_protection_spin.blockSignals(True)
        try:
            self._background_protection_spin.setValue(clamped)
        finally:
            self._background_protection_spin.blockSignals(blocked)
        self._background_protection = clamped
        self._backdrop.set_protection(clamped)
        self.roll.set_background_protection(clamped)
        if persist:
            self._settings.setValue("appearance/background_protection", clamped)
        self._refresh_background_info()

    def set_theme(self, theme_id: str, *, persist: bool = True) -> None:
        """Apply a named UI theme without changing project style metadata."""
        selected = theme_id if theme_id in dict(_THEME_PRESETS) else "dark-gothic"
        self._theme_id = selected
        blocked = self._theme_combo.blockSignals(True)
        try:
            self._theme_combo.setCurrentIndex(max(0, self._theme_combo.findData(selected)))
        finally:
            self._theme_combo.blockSignals(blocked)
        self.setStyleSheet(_theme_style(selected))
        if hasattr(self, "roll"):
            self.roll.set_theme(selected)
        if hasattr(self, "_backdrop"):
            self._backdrop.set_theme(selected)
        if persist:
            self._settings.setValue("appearance/theme", selected)

    def _theme_changed(self, _index: int) -> None:
        theme_id = self._theme_combo.currentData()
        if isinstance(theme_id, str):
            self.set_theme(theme_id)

    def _background_fit_changed(self, _index: int) -> None:
        fit_mode = self._background_fit_combo.currentData()
        if isinstance(fit_mode, str):
            self.set_background_fit(fit_mode)

    def _background_protection_changed(self, value: float) -> None:
        self._background_protection = self._unit_value(value, 0.44)
        if hasattr(self, "_backdrop"):
            self._backdrop.set_protection(self._background_protection)
        if hasattr(self, "roll"):
            self.roll.set_background_protection(self._background_protection)
        self._settings.setValue("appearance/background_protection", self._background_protection)
        if hasattr(self, "_background_info"):
            self._refresh_background_info()

    def _reset_appearance(self) -> None:
        self.set_theme("dark-gothic")
        self.set_background_image(None)
        self.set_background_opacity(0.18)
        self.set_background_fit("cover")
        self.set_background_protection(0.44)
        self.statusBar().showMessage("Appearance restored")

    def _choose_background(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Background Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if selected:
            self.set_background_image(selected)

    def _clear_background(self) -> None:
        self.set_background_image(None)
        self.statusBar().showMessage("Background cleared")

    def _background_opacity_changed(self, value: float) -> None:
        self._background_opacity = self._unit_value(value, 0.18)
        if hasattr(self, "_backdrop"):
            self._backdrop.set_opacity(self._background_opacity)
        if hasattr(self, "roll"):
            self.roll.set_background_opacity(self._background_opacity)
        self._settings.setValue("appearance/background_opacity", self._background_opacity)
        if hasattr(self, "_background_info"):
            self._refresh_background_info()

    @staticmethod
    def _setting_int(settings: QSettings, key: str, default: int) -> int:
        raw_value = settings.value(key, default)
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return default

    def _read_midi_mapping(self) -> MidiKeyboardMapping:
        try:
            return MidiKeyboardMapping(
                lowest_note=self._setting_int(self._settings, "midi/lowest_note", 0),
                key_count=self._setting_int(self._settings, "midi/key_count", 128),
                target_lowest_note=self._setting_int(self._settings, "midi/target_lowest_note", 0),
            )
        except ValueError:
            return MidiKeyboardMapping()

    def _midi_mapping_changed(self, _value: int) -> None:
        lowest = self._midi_lowest_spin.value()
        key_count = min(self._midi_key_count_spin.value(), 128 - lowest)
        target_lowest = min(self._midi_target_spin.value(), 128 - key_count)
        blocked = [
            self._midi_lowest_spin.blockSignals(True),
            self._midi_key_count_spin.blockSignals(True),
            self._midi_target_spin.blockSignals(True),
        ]
        try:
            self._midi_key_count_spin.setRange(1, 128 - lowest)
            self._midi_key_count_spin.setValue(key_count)
            self._midi_target_spin.setRange(0, 128 - key_count)
            self._midi_target_spin.setValue(target_lowest)
        finally:
            self._midi_lowest_spin.blockSignals(blocked[0])
            self._midi_key_count_spin.blockSignals(blocked[1])
            self._midi_target_spin.blockSignals(blocked[2])
        self._midi_mapping = MidiKeyboardMapping(lowest, key_count, target_lowest)
        if self._midi_input is not None:
            self._midi_input.set_mapping(self._midi_mapping)
        self._settings.setValue("midi/lowest_note", lowest)
        self._settings.setValue("midi/key_count", key_count)
        self._settings.setValue("midi/target_lowest_note", target_lowest)
        self._refresh_midi_info()

    def _refresh_midi_info(self) -> None:
        source_low = PianoRollView._pitch_label(self._midi_mapping.lowest_note)
        source_high = PianoRollView._pitch_label(
            self._midi_mapping.lowest_note + self._midi_mapping.key_count - 1
        )
        target_low = PianoRollView._pitch_label(self._midi_mapping.target_lowest_note)
        target_high = PianoRollView._pitch_label(
            self._midi_mapping.target_lowest_note + self._midi_mapping.key_count - 1
        )
        if self._midi_input is None:
            device = "No MIDI input selected"
        else:
            device = f"Connected: {self._midi_input.name}"
        self._midi_info.setText(
            f"{device}\n{self._midi_mapping.key_count} keys: "
            f"{source_low}-{source_high} -> {target_low}-{target_high}"
        )

    def _release_midi_output_notes(self) -> None:
        output = self.player.output
        if output is None:
            self._midi_output_notes.clear()
            return
        for channel, note in tuple(self._midi_output_notes):
            try:
                output.send(MidiKeyboardEvent("note_off", note, note, 0, channel).to_message())
            except (OSError, RuntimeError, ValueError):
                break
        self._midi_output_notes.clear()

    def _close_midi_input(self) -> None:
        self._release_midi_output_notes()
        if self._midi_input is not None:
            self._midi_input.close()
            self._midi_input = None
        self._midi_record_active.clear()
        self._refresh_midi_info()

    def _refresh_midi_inputs(self) -> None:
        selected = self._settings.value("midi/input_name", "")
        selected = selected if isinstance(selected, str) else ""
        try:
            names = midi_input_names()
        except (OSError, RuntimeError, ValueError):
            names = ()
        blocked = self._midi_input_combo.blockSignals(True)
        try:
            self._midi_input_combo.clear()
            self._midi_input_combo.addItem("No MIDI input", None)
            for name in names:
                self._midi_input_combo.addItem(name, name)
            index = self._midi_input_combo.findData(selected)
            self._midi_input_combo.setCurrentIndex(max(index, 0))
        finally:
            self._midi_input_combo.blockSignals(blocked)
        self._midi_input_changed(self._midi_input_combo.currentIndex())
        if not names:
            self.statusBar().showMessage("No MIDI input devices detected")

    def _midi_input_changed(self, _index: int) -> None:
        self._close_midi_input()
        name = self._midi_input_combo.currentData()
        if not isinstance(name, str) or not name:
            self._settings.remove("midi/input_name")
            return
        input_port = open_midi_input(name, self._midi_bridge.event_received.emit, self._midi_mapping)
        if input_port is None:
            self._settings.remove("midi/input_name")
            self.statusBar().showMessage(f"MIDI input unavailable: {name}")
            return
        self._midi_input = input_port
        self._settings.setValue("midi/input_name", name)
        self._refresh_midi_info()
        self.statusBar().showMessage(f"MIDI input connected: {name}")

    def _midi_record_toggled(self, enabled: bool) -> None:
        self._midi_record_active.clear()
        self._midi_record_anchor_tick = self._position_slider.value()
        self._midi_record_anchor_time = monotonic()
        self.statusBar().showMessage("MIDI recording armed" if enabled else "MIDI recording disarmed")

    def _midi_record_tick(self) -> int:
        elapsed = max(0.0, monotonic() - self._midi_record_anchor_time)
        ticks_per_second = self.project.ppq * self.project.tempo_bpm / 60.0
        return max(0, self._midi_record_anchor_tick + round(elapsed * ticks_per_second))

    def _on_midi_event(self, event: object) -> None:
        if not isinstance(event, MidiKeyboardEvent):
            return
        output_error = False
        if self._midi_thru_check.isChecked():
            output = self.player.output
            if output is None:
                try:
                    output = open_default_output()
                    if output is not None:
                        self.player.set_output(output)
                except (OSError, RuntimeError, ValueError):
                    output_error = True
            if output is not None:
                try:
                    output.send(event.to_message())
                    key = (event.channel, event.note)
                    if event.kind == "note_on":
                        self._midi_output_notes.add(key)
                    else:
                        self._midi_output_notes.discard(key)
                except (OSError, RuntimeError, ValueError):
                    output_error = True
        if self._midi_record_check.isChecked():
            track = self._current_track()
            if track is not None:
                key = (event.channel, event.note)
                if event.kind == "note_on":
                    self._midi_record_active[key] = (self._midi_record_tick(), event.velocity)
                else:
                    started = self._midi_record_active.pop(key, None)
                    if started is not None:
                        start_tick, velocity = started
                        duration = max(1, self._midi_record_tick() - start_tick)
                        self.command_stack.execute(
                            AddNoteCommand(
                                self.project,
                                self.track_list.currentRow(),
                                Note(start_tick, duration, event.note, velocity),
                            )
                        )
        if output_error:
            self.statusBar().showMessage("MIDI output disconnected")
        else:
            self.statusBar().showMessage(
                f"MIDI {event.kind.replace('_', ' ')}: {PianoRollView._pitch_label(event.note)}"
            )

    def _update_position_range(self) -> None:
        end_tick = max((note.end_tick for track in self.project.tracks for note in track.notes), default=1)
        self._position_slider.setRange(0, max(1, end_tick))
        if self.player.position_tick > end_tick:
            self._position_slider.setValue(end_tick)

    def _sync_playback_cursor(self) -> None:
        position = getattr(self.player, "position_tick", 0)
        if isinstance(position, int):
            self.roll.set_playback_tick(position)
            blocked = self._position_slider.blockSignals(True)
            self._position_slider.setValue(position)
            self._position_slider.blockSignals(blocked)
        if not getattr(self.player, "is_playing", False):
            self._playback_timer.stop()

    def _seek_changed(self, value: int) -> None:
        if not self._ready:
            return
        try:
            self.player.seek(value)
        except (AttributeError, ValueError):
            return
        self.roll.set_playback_tick(value)
        self.statusBar().showMessage(f"Position: {value} ticks")

    def _sync_track_controls(self) -> None:
        if not hasattr(self, "_volume_spin") or not hasattr(self, "_pan_spin"):
            return
        track = self._current_track()
        blocked_volume = self._volume_spin.blockSignals(True)
        blocked_pan = self._pan_spin.blockSignals(True)
        try:
            enabled = track is not None
            self._volume_spin.setEnabled(enabled)
            self._pan_spin.setEnabled(enabled)
            if track is not None:
                self._volume_spin.setValue(track.volume)
                self._pan_spin.setValue(track.pan)
        finally:
            self._volume_spin.blockSignals(blocked_volume)
            self._pan_spin.blockSignals(blocked_pan)

    def _volume_changed(self, value: float) -> None:
        track = self._current_track()
        if track is None:
            return
        track.volume = value
        self._dirty = True
        self._autosave()
        self._update_window_title()

    def _pan_changed(self, value: float) -> None:
        track = self._current_track()
        if track is None:
            return
        track.pan = value
        self._dirty = True
        self._autosave()
        self._update_window_title()

    def _style_changed(self, _index: int) -> None:
        style_id = self.style_combo.currentData()
        if not isinstance(style_id, str):
            return
        preset = get_style_preset(style_id)
        self.project.style_preset_id = style_id
        self.tempo_spin.setRange(max(30.0, preset.tempo_min), min(300.0, preset.tempo_max))
        self.tempo_spin.setValue(min(max(self.project.tempo_bpm, preset.tempo_min), preset.tempo_max))
        self._refresh_info()
        self._dirty = True
        self._autosave()
        self._update_window_title()
        self.statusBar().showMessage(f"Style: {preset.name}")

    def _tempo_changed(self, value: float) -> None:
        self.project.tempo_bpm = value
        self._refresh_info()
        self._dirty = True
        self._autosave()
        self._update_window_title()

    def _pack_changed(self, _index: int) -> None:
        manifest_value = self.pack_combo.currentData()
        if isinstance(manifest_value, str):
            try:
                self.project.sound_pack_id = SoundPackManifest.load(manifest_value).id
            except (OSError, SoundPackError, ValueError, KeyError, TypeError):
                pass
            if self._ready:
                self._dirty = True
                self._autosave()
                self._update_window_title()
        self._refresh_info()

    def _select_project_pack(self) -> None:
        if not self.project.sound_pack_id:
            return
        for index in range(self.pack_combo.count()):
            manifest_path = self.pack_combo.itemData(index)
            try:
                if SoundPackManifest.load(manifest_path).id == self.project.sound_pack_id:
                    self.pack_combo.setCurrentIndex(index)
                    return
            except (OSError, SoundPackError, ValueError, KeyError, TypeError):
                continue

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

    def _set_transcription_idle(self) -> None:
        """Restore controls after a transcription job finishes or is cancelled."""
        self._transcription_timer.stop()
        self._import_button.setEnabled(True)
        self._cancel_import_button.setEnabled(False)

    def _finish_transcription_failure(self, error: str, *, detail: str | None = None) -> None:
        """Clear a failed job without allowing a worker callback to break the UI."""
        if detail is not None:
            self._write_transcription_log("error", detail)
        self._pending_transcription = None
        self._accept_button.setEnabled(False)
        self._candidate_info.setText(f"Transcription failed: {error}")
        self._set_transcription_idle()
        self.statusBar().showMessage("Transcription failed; project is unchanged")

    def import_audio(self, path: str | Path | None = None) -> None:
        """Start a cancellable Basic Pitch job and poll it from the Qt event loop."""
        if self._transcription_process is not None and self._transcription_process.is_running:
            self.statusBar().showMessage("Transcription already running")
            return
        if path is None:
            selected, _ = QFileDialog.getOpenFileName(
                self, "Import Audio", "", "Audio (*.wav *.flac *.ogg *.mp3)"
            )
            if not selected:
                self.statusBar().showMessage("Audio import cancelled")
                return
            path = selected
        request = TranscriptionRequest(str(path), cache_dir=str(Path.cwd() / ".siegfridi" / "audio-cache"))
        try:
            self._transcription_process = TranscriptionProcess(request)
            self._transcription_process.start()
        except (OSError, RuntimeError, ValueError) as exc:
            self._transcription_process = None
            self._write_transcription_log("start-failed", str(exc))
            self.statusBar().showMessage(f"Transcription failed: {exc}")
            self._candidate_info.setText(f"Transcription failed: {exc}")
            return
        self._import_button.setEnabled(False)
        self._cancel_import_button.setEnabled(True)
        self._accept_button.setEnabled(False)
        self._candidate_info.setText("Transcribing...")
        self._transcription_timer.start()
        self.statusBar().showMessage(f"Transcribing: {path}")

    def _poll_transcription(self) -> None:
        process = self._transcription_process
        if process is None:
            self._transcription_timer.stop()
            return
        try:
            messages = process.poll()
        except (OSError, RuntimeError, ValueError) as exc:
            self._finish_transcription_failure(str(exc), detail=str(exc))
            try:
                process.close()
            except (OSError, RuntimeError, ValueError):
                pass
            self._transcription_process = None
            return
        invalid_response = False
        for message in messages:
            if not isinstance(message, dict):
                self._finish_transcription_failure("invalid worker response", detail=repr(message))
                invalid_response = True
                break
            message_type = message.get("type")
            if message_type == "completed" and isinstance(message.get("result"), TranscriptionResult):
                self._pending_transcription = message["result"]
                self._refresh_candidate_info()
                self._accept_button.setEnabled(True)
                self.statusBar().showMessage("Transcription ready - review candidates")
            elif message_type == "failed":
                error = str(message.get("error", "unknown transcription error"))
                self._write_transcription_log(str(message.get("error_type", "error")), error)
                self._candidate_info.setText(f"Transcription failed: {error}")
                self._pending_transcription = None
                self._accept_button.setEnabled(False)
                self.statusBar().showMessage("Transcription failed; project is unchanged")
        if invalid_response:
            try:
                process.close()
            except (OSError, RuntimeError, ValueError):
                pass
            self._transcription_process = None
            return
        if not process.is_running:
            self._set_transcription_idle()
            try:
                process.close()
            except (OSError, RuntimeError, ValueError) as exc:
                self._write_transcription_log("close-failed", str(exc))
                self.statusBar().showMessage(f"Transcription cleanup warning: {exc}")
            self._transcription_process = None

    def _refresh_candidate_info(self, _value: float | None = None) -> None:
        result = self._pending_transcription
        if result is None:
            return
        summary = summarize_candidates(result, self._confidence_spin.value())
        warning = f" | {len(result.warnings)} warning(s)" if result.warnings else ""
        self._candidate_info.setText(
            f"{summary.accepted}/{summary.total} candidates | BPM {summary.bpm:.1f} | "
            f"confidence >= {summary.minimum_confidence:.2f}{warning}"
        )

    def accept_transcription(self) -> None:
        result = self._pending_transcription
        if result is None:
            return
        try:
            track = append_result_track(
                self.project,
                result,
                track_name=f"Transcription: {Path(result.source).stem}",
                minimum_confidence=self._confidence_spin.value(),
                grid_tick=self._quantize_spin.value(),
            )
        except (OSError, ValueError, TypeError) as exc:
            self.statusBar().showMessage(f"Transcription accept failed: {exc}")
            self._candidate_info.setText(f"Could not accept transcription: {exc}")
            return
        self._pending_transcription = None
        self._accept_button.setEnabled(False)
        self._populate_tracks()
        self.track_list.setCurrentRow(len(self.project.tracks) - 1)
        self._update_position_range()
        self._dirty = True
        self._autosave()
        self._update_window_title()
        self._candidate_info.setText(f"Accepted {len(track.notes)} notes into {track.name}")
        self.statusBar().showMessage("Transcription candidates accepted")

    def cancel_transcription(self) -> None:
        process = self._transcription_process
        cancel_error: str | None = None
        if process is not None:
            try:
                process.cancel()
            except (OSError, RuntimeError, ValueError) as exc:
                cancel_error = str(exc)
            try:
                process.close()
            except (OSError, RuntimeError, ValueError) as exc:
                cancel_error = cancel_error or str(exc)
            request = getattr(process, "request", None)
            self._write_transcription_log("cancelled", str(getattr(request, "audio_path", "unknown")))
        self._transcription_process = None
        self._set_transcription_idle()
        self._pending_transcription = None
        self._accept_button.setEnabled(False)
        self._candidate_info.setText("Transcription cancelled; project is unchanged")
        if process is not None:
            message = "Transcription cancelled"
            if cancel_error:
                message = f"Transcription cancelled; cleanup warning: {cancel_error}"
            self.statusBar().showMessage(message)
        else:
            self.statusBar().showMessage("No transcription running")

    def _write_transcription_log(self, event: str, detail: str) -> None:
        log_path = Path.cwd() / ".siegfridi" / "transcription.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).isoformat()
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(f"{timestamp}\t{event}\t{detail}\n")
        except OSError as exc:
            self.statusBar().showMessage(f"Transcription log unavailable: {exc}")

    def _play(self) -> None:
        try:
            if self.player.output is None:
                output = open_default_output()
                if output is not None:
                    self.player.set_output(output)
            start_tick = self._position_slider.value()
            if start_tick:
                self.player.start(self.project, start_tick)
            else:
                self.player.start(self.project)
        except (OSError, RuntimeError, ValueError) as exc:
            self._playback_timer.stop()
            self.statusBar().showMessage(f"Playback failed: {exc}")
            return
        self._playback_timer.start()
        message = "Playing" if self.player.output is not None else "Playing (no MIDI output device)"
        self.statusBar().showMessage(message)

    def _toggle_pause(self) -> None:
        if not getattr(self.player, "is_playing", False):
            self.statusBar().showMessage("Playback is not running")
            return
        try:
            if getattr(self.player, "is_paused", False):
                self.player.resume()
                self._pause_button.setText("Pause")
                self.statusBar().showMessage("Playing")
            else:
                self.player.pause()
                self._pause_button.setText("Resume")
                self.statusBar().showMessage("Paused")
        except (OSError, RuntimeError, ValueError) as exc:
            self.statusBar().showMessage(f"Pause/resume failed: {exc}")

    def _stop_playback(self) -> None:
        stop_error: str | None = None
        try:
            self.player.stop()
        except (OSError, RuntimeError, ValueError) as exc:
            stop_error = str(exc)
        self._playback_timer.stop()
        self._pause_button.setText("Pause")
        blocked = self._position_slider.blockSignals(True)
        self._position_slider.setValue(0)
        self._position_slider.blockSignals(blocked)
        self.roll.set_playback_tick(0)
        self.statusBar().showMessage(
            f"Stop playback failed: {stop_error}" if stop_error else "Playback stopped"
        )

    def new_project(self) -> None:
        self._replace_project(Project(tracks=[Track(name="Track 1")]))
        self.project_path = None
        self._dirty = False
        self._update_window_title()
        self.statusBar().showMessage("New project")

    def _replace_project(self, project: Project) -> None:
        self._stop_playback()
        self.project = project
        self.roll.set_project(project)
        self._populate_tracks()
        self.style_combo.blockSignals(True)
        try:
            index = self.style_combo.findData(project.style_preset_id)
            self.style_combo.setCurrentIndex(max(0, index))
        finally:
            self.style_combo.blockSignals(False)
        self.tempo_spin.blockSignals(True)
        self.tempo_spin.setValue(project.tempo_bpm)
        self.tempo_spin.blockSignals(False)
        self._select_project_pack()
        self.command_stack.clear()
        self._update_position_range()
        self._sync_track_controls()
        self._refresh_info()

    def open_project(self, path: str | Path | None = None) -> Path | None:
        # QAction.triggered(bool) supplies a checked flag; it is not a path.
        if isinstance(path, bool):
            path = None
        if path is None:
            selected, _ = QFileDialog.getOpenFileName(
                self, "Open Siegfridi Project", "", "Siegfridi Project (*.siegfridi)"
            )
            if not selected:
                self.statusBar().showMessage("Open cancelled")
                return None
            path = selected
        try:
            project = load_siegfridi(path)
        except (OSError, ProjectFileError) as exc:
            self.statusBar().showMessage(f"Open failed: {exc}")
            return None
        self._replace_project(project)
        self.project_path = Path(path)
        self._dirty = False
        self._update_window_title()
        self.statusBar().showMessage(f"Opened: {self.project_path}")
        return self.project_path

    def save_project(self, path: str | Path | None = None) -> Path | None:
        # QAction.triggered(bool) supplies a checked flag; it is not a path.
        if isinstance(path, bool):
            path = None
        destination = Path(path) if path is not None else self.project_path
        if destination is None:
            selected, _ = QFileDialog.getSaveFileName(
                self, "Save Siegfridi Project", "", "Siegfridi Project (*.siegfridi)"
            )
            if not selected:
                self.statusBar().showMessage("Save cancelled")
                return None
            destination = Path(selected)
            if destination.suffix.lower() != ".siegfridi":
                destination = destination.with_suffix(".siegfridi")
        try:
            saved = save_siegfridi(self.project, destination)
        except (OSError, ProjectFileError) as exc:
            self.statusBar().showMessage(f"Save failed: {exc}")
            return None
        self.project_path = saved
        self._dirty = False
        self._update_window_title()
        self.statusBar().showMessage(f"Saved: {saved}")
        return saved

    def _current_track(self) -> Track | None:
        row = self.track_list.currentRow()
        return self.project.tracks[row] if 0 <= row < len(self.project.tracks) else None

    def _toggle_mute(self) -> None:
        track = self._current_track()
        if track is None:
            self.statusBar().showMessage("Select a track before muting")
            return
        track.muted = not track.muted
        self._populate_tracks()
        self.track_list.setCurrentRow(self.project.tracks.index(track))
        self._refresh_info()
        self._dirty = True
        self._autosave()
        self._update_window_title()
        self.statusBar().showMessage(f"{track.name}: {'muted' if track.muted else 'unmuted'}")

    def _toggle_solo(self) -> None:
        track = self._current_track()
        if track is None:
            self.statusBar().showMessage("Select a track before enabling solo")
            return
        track.solo = not track.solo
        self._populate_tracks()
        self.track_list.setCurrentRow(self.project.tracks.index(track))
        self._refresh_info()
        self._dirty = True
        self._autosave()
        self._update_window_title()
        self.statusBar().showMessage(f"{track.name}: {'solo' if track.solo else 'not solo'}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.cancel_transcription()
        self._close_midi_input()
        self._stop_playback()
        output = self.player.output
        close = getattr(output, "close", None)
        if close is not None:
            try:
                close()
            except (OSError, RuntimeError, ValueError) as exc:
                self.statusBar().showMessage(f"MIDI output close failed: {exc}")
        super().closeEvent(event)


def launch() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
