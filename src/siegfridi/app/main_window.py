"""Main Qt workbench for the development editor slice."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.editing import CommandStack
from ..core.models import Note, Project, Track
from ..core.project_io import ProjectFileError, autosave_project, load_siegfridi, save_siegfridi
from ..playback import MidiPlayer, open_default_output
from ..sound import SoundPackError, SoundPackManifest
from ..sound.presets import BUILTIN_STYLE_PRESETS, get_style_preset
from ..synthesis import SynthesisError, render_manifest
from ..transcription import TranscriptionResult, append_result_track, summarize_candidates
from ..workers.transcription import TranscriptionProcess, TranscriptionRequest
from .piano_roll import PianoRollView


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

        self.roll = PianoRollView(self.project, self.command_stack)
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
        self.render_button.clicked.connect(self._render_preview)
        if self.pack_combo.count() == 0:
            self.render_button.setEnabled(False)

        self._import_button = QPushButton("Import audio")
        self._import_button.setToolTip("Run Basic Pitch and prepare candidate notes")
        self._import_button.clicked.connect(self.import_audio)
        self._cancel_import_button = QPushButton("Cancel import")
        self._cancel_import_button.setEnabled(False)
        self._cancel_import_button.clicked.connect(self.cancel_transcription)
        self._accept_button = QPushButton("Accept candidates")
        self._accept_button.setEnabled(False)
        self._accept_button.clicked.connect(self.accept_transcription)

        self._project_info = QLabel()
        self._project_info.setWordWrap(True)
        self._pack_info = QLabel()
        self._pack_info.setWordWrap(True)
        self._style_info = QLabel()
        self._style_info.setWordWrap(True)
        self._refresh_info()

        self._play_button = QPushButton("Play")
        self._pause_button = QPushButton("Pause")
        self._stop_button = QPushButton("Stop")
        self._mute_button = QPushButton("Mute track")
        self._solo_button = QPushButton("Solo track")
        self._play_button.clicked.connect(self._play)
        self._pause_button.clicked.connect(self._toggle_pause)
        self._stop_button.clicked.connect(self._stop_playback)
        self._mute_button.clicked.connect(self._toggle_mute)
        self._solo_button.clicked.connect(self._toggle_solo)

        toolbar = QToolBar("Edit")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_project)
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        toolbar.addAction(new_action)
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addSeparator()
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
        toolbar.addWidget(self._pause_button)
        toolbar.addWidget(self._stop_button)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        project_group = QGroupBox("Project")
        project_form = QFormLayout(project_group)
        project_form.addRow("Style", self.style_combo)
        project_form.addRow("Tempo", self.tempo_spin)
        project_form.addRow("Position", self._position_slider)
        project_form.addRow(self._style_info)
        panel_layout.addWidget(project_group)

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

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)
        layout.addWidget(self.roll, 1)
        self.setCentralWidget(central)
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

    def _update_position_range(self) -> None:
        end_tick = max((note.end_tick for track in self.project.tracks for note in track.notes), default=1)
        self._position_slider.setRange(0, max(1, end_tick))
        if self.player.position_tick > end_tick:
            self._position_slider.setValue(end_tick)

    def _sync_playback_cursor(self) -> None:
        position = getattr(self.player, "position_tick", 0)
        if isinstance(position, int):
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
        self.statusBar().showMessage(f"Position: {value} ticks")

    def _sync_track_controls(self) -> None:
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
        messages = process.poll()
        for message in messages:
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
                self.statusBar().showMessage("Transcription failed; project is unchanged")
        if not process.is_running:
            self._transcription_timer.stop()
            self._import_button.setEnabled(True)
            self._cancel_import_button.setEnabled(False)
            process.close()
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
        track = append_result_track(
            self.project,
            result,
            track_name=f"Transcription: {Path(result.source).stem}",
            minimum_confidence=self._confidence_spin.value(),
            grid_tick=self._quantize_spin.value(),
        )
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
        if process is not None:
            process.cancel()
            process.close()
            self._write_transcription_log("cancelled", process.request.audio_path)
        self._transcription_process = None
        self._transcription_timer.stop()
        self._import_button.setEnabled(True)
        self._cancel_import_button.setEnabled(False)
        self._pending_transcription = None
        self._accept_button.setEnabled(False)
        self._candidate_info.setText("Transcription cancelled; project is unchanged")
        self.statusBar().showMessage("Transcription cancelled")

    def _write_transcription_log(self, event: str, detail: str) -> None:
        log_path = Path.cwd() / ".siegfridi" / "transcription.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).isoformat()
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{timestamp}\t{event}\t{detail}\n")

    def _play(self) -> None:
        if self.player.output is None:
            output = open_default_output()
            if output is not None:
                self.player.set_output(output)
        start_tick = self._position_slider.value()
        if start_tick:
            self.player.start(self.project, start_tick)
        else:
            self.player.start(self.project)
        self._playback_timer.start()
        message = "Playing" if self.player.output is not None else "Playing (no MIDI output device)"
        self.statusBar().showMessage(message)

    def _toggle_pause(self) -> None:
        if not getattr(self.player, "is_playing", False):
            return
        if getattr(self.player, "is_paused", False):
            self.player.resume()
            self._pause_button.setText("Pause")
            self.statusBar().showMessage("Playing")
        else:
            self.player.pause()
            self._pause_button.setText("Resume")
            self.statusBar().showMessage("Paused")

    def _stop_playback(self) -> None:
        self.player.stop()
        self._playback_timer.stop()
        self._pause_button.setText("Pause")
        blocked = self._position_slider.blockSignals(True)
        self._position_slider.setValue(0)
        self._position_slider.blockSignals(blocked)

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
        if path is None:
            selected, _ = QFileDialog.getOpenFileName(
                self, "Open Siegfridi Project", "", "Siegfridi Project (*.siegfridi)"
            )
            if not selected:
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
        destination = Path(path) if path is not None else self.project_path
        if destination is None:
            selected, _ = QFileDialog.getSaveFileName(
                self, "Save Siegfridi Project", "", "Siegfridi Project (*.siegfridi)"
            )
            if not selected:
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
        self._stop_playback()
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
