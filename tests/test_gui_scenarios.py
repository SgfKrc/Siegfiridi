import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from siegfridi.app.main_window import MainWindow
from siegfridi.app.piano_roll import PianoRollNoteItem, PianoRollView
from siegfridi.core.editing import CommandStack
from siegfridi.core.models import Note, Project, Track
from siegfridi.midi import MidiKeyboardEvent
from siegfridi.synthesis import SynthesisError
from siegfridi.transcription import CandidateNote, TranscriptionResult


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _scene_point(view: PianoRollView, tick: int, pitch: int, offset_y: float = 5.0) -> QPoint:
    scene_point = QPointF(view._tick_to_x(tick), view._pitch_to_y(pitch) + offset_y)
    return view.mapFromScene(scene_point)


def test_piano_roll_mouse_workflow_covers_editing_gestures(qapp: QApplication) -> None:
    project = Project(
        tracks=[
            Track("Lead", notes=[Note(480, 480, 100)]),
            Track("Pad", notes=[Note(0, 240, 80)]),
        ]
    )
    stack = CommandStack()
    view = PianoRollView(project, stack)
    view.resize(800, 600)
    view.show()
    qapp.processEvents()
    viewport = view.viewport()

    # Blank click creates a snapped note, then the keyboard path removes it.
    blank = _scene_point(view, 240, 90)
    QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=blank)
    assert project.tracks[0].notes[0] == Note(240, 240, 90)
    assert view.selected_note_index == 0
    QTest.keyClick(view, Qt.Key.Key_Delete)
    assert project.tracks[0].notes == [Note(480, 480, 100)]

    # Select and release without movement to cover the no-op drag path.
    interior = _scene_point(view, 600, 100)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=interior)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=interior)
    assert project.tracks[0].notes[0] == Note(480, 480, 100)

    # Drag the note to a new tick/pitch, then exercise undo and redo shortcuts.
    move_to = _scene_point(view, 1080, 90)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=interior)
    QTest.mouseMove(viewport, move_to)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=move_to)
    assert project.tracks[0].notes[0] == Note(960, 480, 90, 100)
    QTest.keyClick(view, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert project.tracks[0].notes[0] == Note(480, 480, 100)
    QTest.keyClick(view, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert project.tracks[0].notes[0] == Note(960, 480, 90, 100)

    # Resize from the right handle and delete through the context menu gesture.
    resize_start = _scene_point(view, 1420, 90)
    resize_end = _scene_point(view, 1800, 90)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=resize_start)
    QTest.mouseMove(viewport, resize_end)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=resize_end)
    assert project.tracks[0].notes[0] == Note(960, 840, 90, 100)
    QTest.mouseClick(viewport, Qt.MouseButton.RightButton, pos=_scene_point(view, 1080, 90))
    assert project.tracks[0].notes == []

    # Cover the wheel zoom branch and the normal wheel delegation branch.
    wheel_pos = QPointF(viewport.width() / 2, viewport.height() / 2)
    zoom_event = QWheelEvent(
        wheel_pos,
        wheel_pos,
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(viewport, zoom_event)
    normal_event = QWheelEvent(
        wheel_pos,
        wheel_pos,
        QPoint(0, -120),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(viewport, normal_event)
    QTest.keyClick(view, Qt.Key.Key_A)
    view.close()
    qapp.processEvents()


def test_piano_roll_project_and_track_boundaries(qapp: QApplication) -> None:
    view = PianoRollView(Project(), CommandStack())
    view.set_track(4)
    assert view.track_index == 0
    view.set_project(Project(tracks=[Track("Lead")]))
    with pytest.raises(IndexError):
        view.set_track(1)
    view.set_project(Project())
    view.close()
    qapp.processEvents()


def test_piano_roll_selection_mode_copies_track_and_previews_offset_paste(
    qapp: QApplication,
) -> None:
    project = Project(
        tracks=[
            Track("Lead", notes=[Note(0, 240, 60), Note(240, 360, 64)]),
            Track("Target"),
        ]
    )
    view = PianoRollView(project, CommandStack())
    view.resize(800, 600)
    view.show()
    qapp.processEvents()

    assert not view.selection_mode
    view.set_selection_mode(True)
    assert view.selection_mode
    assert view.viewport().cursor().shape() == Qt.CursorShape.CrossCursor

    marquee_start = _scene_point(view, 0, 70)
    marquee_end = _scene_point(view, 700, 55)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=marquee_start)
    QTest.mouseMove(view.viewport(), marquee_end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=marquee_end)
    assert view.selected_note_indices == frozenset({0, 1})

    view._clear_selection()
    first = _scene_point(view, 60, 60)
    second = _scene_point(view, 300, 64)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        second,
    )
    assert view.selected_note_indices == frozenset({0, 1})
    assert view.copy_selection() == 2
    assert view.has_clipboard
    assert len(view.paste_preview_items) == 2

    view.set_track(1)
    view.set_paste_anchor(960, 72)
    assert view.paste_anchor == (960, 72)
    assert len(view.paste_preview_items) == 2
    assert view.paste_preview_items[0].brush().color().alpha() < 255
    assert view.paste_selection() == 2
    assert project.tracks[1].notes == [Note(960, 240, 72), Note(1200, 360, 76)]
    assert view.paste_anchor is None

    assert view.command_stack.undo()
    assert project.tracks[1].notes == []
    view.set_selection_mode(False)
    assert view.viewport().cursor().shape() == Qt.CursorShape.ArrowCursor
    view.close()
    qapp.processEvents()


def test_selection_mode_shortcuts_clamp_transposition_and_clear_preview(qapp: QApplication) -> None:
    project = Project(
        tracks=[
            Track("Source", notes=[Note(0, 240, 120), Note(120, 240, 124)]),
            Track("Target"),
        ]
    )
    view = PianoRollView(project, CommandStack())
    view.resize(800, 600)
    view.show()
    view.set_selection_mode(True)
    qapp.processEvents()

    source_note = _scene_point(view, 60, 120)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=source_note)
    second_source_note = _scene_point(view, 180, 124)
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        second_source_note,
    )
    view.setFocus()
    QTest.keyClick(view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert view.has_clipboard

    view.set_track(1)
    assert view.set_paste_anchor(-120, 127)
    assert view.paste_anchor == (0, 123)
    assert [item.rect().y() for item in view.paste_preview_items]
    QTest.keyClick(view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert project.tracks[1].notes == [Note(0, 240, 123), Note(120, 240, 127)]

    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.selected_note_indices == frozenset()
    assert not view.has_clipboard
    assert view.paste_preview_items == ()
    view.close()
    qapp.processEvents()


def test_selection_mode_empty_track_reports_no_copy_or_paste(qapp: QApplication) -> None:
    view = PianoRollView(Project(tracks=[Track("Empty")]), CommandStack())
    copied: list[int] = []
    pasted: list[int] = []
    view.copy_completed.connect(copied.append)
    view.paste_completed.connect(pasted.append)
    view.set_selection_mode(True)

    assert view.copy_selection() == 0
    assert view.set_paste_anchor(480, 60) is False
    assert view.paste_selection() == 0
    assert copied == [0]
    assert pasted == [0]
    view.close()
    qapp.processEvents()


def test_piano_roll_pitch_keyboard_is_read_only_and_labeled(qapp: QApplication) -> None:
    project = Project(tracks=[Track("Lead")])
    view = PianoRollView(project, CommandStack())
    view.resize(800, 600)
    view.show()
    qapp.processEvents()

    assert len(view._keyboard_keys) == 128
    assert view._pitch_label(60) == "C4"
    assert view._pitch_label(0) == "C-1"
    assert set(view._keyboard_labels) == set(range(0, 128, 12))

    keyboard_point = view.mapFromScene(QPointF(view.LEFT_MARGIN / 2, view._pitch_to_y(60) + 5))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=keyboard_point)
    assert project.tracks[0].notes == []

    view.close()
    qapp.processEvents()


def test_piano_roll_ruler_and_playback_cursor_are_readable(qapp: QApplication) -> None:
    project = Project(tracks=[Track("Lead", notes=[Note(0, 480, 60)])])
    view = PianoRollView(project, CommandStack())
    view.resize(800, 600)
    view.show()
    qapp.processEvents()

    assert view.scene().sceneRect().height() == pytest.approx(
        view.RULER_HEIGHT + 128 * view.ROW_HEIGHT
    )
    assert view._ruler_labels[0].text() == "0"
    ruler_point = view.mapFromScene(QPointF(view._tick_to_x(240), view.RULER_HEIGHT / 2))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=ruler_point)
    assert project.tracks[0].notes == [Note(0, 480, 60)]

    view.set_playback_tick(960)
    assert view.playback_tick == 960
    assert view._playback_cursor is not None
    assert view._playback_cursor.line().x1() == pytest.approx(view._tick_to_x(960))
    assert view._playback_cursor_label is not None
    assert view._playback_cursor_label.text() == "960"
    view.set_playback_tick(-10)
    assert view.playback_tick == 0

    view.close()
    qapp.processEvents()


def test_piano_roll_large_project_refresh_and_scroll_smoke(qapp: QApplication) -> None:
    notes = [Note(index * 12, 30, 48 + index % 36, 80) for index in range(10_000)]
    view = PianoRollView(Project(tracks=[Track("Dense", notes=notes)]), CommandStack())
    view.resize(800, 600)
    view.show()
    qapp.processEvents()

    note_items = [item for item in view.scene().items() if isinstance(item, PianoRollNoteItem)]
    assert len(note_items) == 10_000
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().maximum())
    view.set_playback_tick(notes[-1].end_tick)
    qapp.processEvents()
    assert view.playback_tick == notes[-1].end_tick
    assert view._playback_cursor is not None
    view.close()
    qapp.processEvents()


def test_main_window_control_workflow(qapp: QApplication, monkeypatch, tmp_path: Path) -> None:
    project = Project(
        tempo_bpm=120,
        style_preset_id="dark-gothic",
        tracks=[
            Track("Lead", role="melody", notes=[Note(0, 240, 72)], muted=True),
            Track("Pad", role="pad", notes=[Note(0, 480, 48)], solo=True),
        ],
    )
    window = MainWindow(project)
    window.show()
    qapp.processEvents()

    assert window._play_button.toolTip()
    assert window._pause_button.statusTip()
    assert "Ctrl+O" in window._open_action.toolTip()
    assert "Ctrl+S" in window._save_action.toolTip()
    assert "Ctrl+Z" in window._undo_action.toolTip()
    assert "Ctrl+Y" in window._redo_action.toolTip()
    window._toggle_pause()
    assert window.statusBar().currentMessage() == "Playback is not running"

    assert "muted" in window.track_list.item(0).text()
    assert "solo" in window.track_list.item(1).text()

    window.style_combo.setCurrentIndex(window.style_combo.findData("retro-rpg"))
    assert project.style_preset_id == "retro-rpg"
    assert window.tempo_spin.minimum() == 90
    window.tempo_spin.setValue(150)
    assert project.tempo_bpm == 150
    window.pack_combo.setCurrentIndex(1)
    assert "profiles:" in window._pack_info.text()

    window.track_list.setCurrentRow(0)
    QTest.mouseClick(window._mute_button, Qt.MouseButton.LeftButton)
    assert project.tracks[0].muted is False
    QTest.mouseClick(window._solo_button, Qt.MouseButton.LeftButton)
    assert project.tracks[0].solo is True

    class FakePlayer:
        def __init__(self) -> None:
            self.output = None
            self.started = False
            self.stopped = False

        def set_output(self, output) -> None:
            self.output = output

        def start(self, _project) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

    fake_player = FakePlayer()
    window.player = fake_player
    window._stop_button.clicked.connect(fake_player.stop)
    monkeypatch.setattr("siegfridi.app.main_window.open_default_output", lambda: None)
    QTest.mouseClick(window._play_button, Qt.MouseButton.LeftButton)
    assert fake_player.started is True
    assert "no MIDI output" in window.statusBar().currentMessage()
    QTest.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)
    assert fake_player.stopped is True
    assert window.statusBar().currentMessage() == "Playback stopped"
    rendered = {}

    def fake_render(project_arg, manifest_arg, output_arg, **kwargs):
        rendered.update(project=project_arg, manifest=manifest_arg, output=output_arg, kwargs=kwargs)
        return output_arg

    monkeypatch.setattr("siegfridi.app.main_window.render_manifest", fake_render)
    monkeypatch.chdir(tmp_path)
    QTest.mouseClick(window.render_button, Qt.MouseButton.LeftButton)
    assert rendered["project"] is project
    assert Path(rendered["output"]).name == "preview.wav"
    assert "Preview rendered" in window.statusBar().currentMessage()

    monkeypatch.setattr(
        "siegfridi.app.main_window.render_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(SynthesisError("test failure")),
    )
    QTest.mouseClick(window.render_button, Qt.MouseButton.LeftButton)
    assert "Preview failed" in window.statusBar().currentMessage()

    window.pack_combo.clear()
    window._render_preview()
    assert "No SoundFont selected" in window.statusBar().currentMessage()
    window.track_list.setCurrentRow(-1)
    monkeypatch.setattr(window, "_current_track", lambda: None)
    window._toggle_mute()
    assert "Select a track" in window.statusBar().currentMessage()
    window._toggle_solo()
    assert "Select a track" in window.statusBar().currentMessage()
    window.close()
    qapp.processEvents()
    assert fake_player.stopped is True


@pytest.mark.parametrize(
    ("width", "height", "theme"),
    ((1440, 900, "dark-gothic"), (1440, 900, "quiet-light"), (900, 700, "high-contrast")),
)
def test_main_window_visual_profiles_fit_without_overflow(
    qapp: QApplication, width: int, height: int, theme: str
) -> None:
    window = MainWindow(Project(tracks=[Track("Lead", notes=[Note(0, 480, 60)])]))
    window.resize(width, height)
    window.set_theme(theme, persist=False)
    window.set_background_image(None, persist=False)
    window.show()
    qapp.processEvents()

    assert (window.width(), window.height()) == (width, height)
    assert window.centralWidget() is not None
    assert window.rect().contains(window.centralWidget().geometry().topLeft())
    assert window.rect().contains(window.centralWidget().geometry().bottomRight())
    workspace = window._control_scroll.parentWidget()
    assert workspace is not None
    for widget in (window._control_scroll, window.roll):
        assert workspace.rect().contains(widget.geometry().topLeft())
        assert workspace.rect().contains(widget.geometry().bottomRight())
        assert widget.width() > 0 and widget.height() > 0
    assert not window._control_scroll.horizontalScrollBar().isVisible()
    assert window._control_scroll.widget().height() > window._control_scroll.viewport().height()
    window.close()
    qapp.processEvents()


def test_main_window_background_image_and_opacity_controls(qapp: QApplication, monkeypatch, tmp_path: Path) -> None:
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(0x003f4f66)
    image_path = tmp_path / "workbench-background.png"
    assert image.save(str(image_path))

    window = MainWindow(Project(tracks=[Track("Lead")]))
    window.show()
    qapp.processEvents()
    assert window.set_background_image(tmp_path / "missing.png") is False
    window.set_background_opacity(2.0)
    assert window._backdrop.opacity == pytest.approx(1.0)
    window.set_background_opacity(-1.0)
    assert window._backdrop.opacity == pytest.approx(0.0)
    monkeypatch.setattr(
        "siegfridi.app.main_window.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(image_path), ""),
    )

    QTest.mouseClick(window._background_button, Qt.MouseButton.LeftButton)
    assert window._background_path == image_path.resolve()
    assert not window.roll._background_pixmap.isNull()
    assert window._background_clear_button.isEnabled()
    window.set_background_opacity(0.42)
    assert window._backdrop.opacity == pytest.approx(0.42)
    assert "42%" in window._background_info.text()

    QTest.mouseClick(window._background_clear_button, Qt.MouseButton.LeftButton)
    assert window._background_path is None
    assert window.roll._background_pixmap.isNull()
    assert not window._background_clear_button.isEnabled()
    window.close()
    qapp.processEvents()


def test_main_window_appearance_preferences_persist_and_restore_defaults(
    qapp: QApplication, tmp_path: Path
) -> None:
    from PySide6.QtCore import QSettings

    image = QImage(48, 24, QImage.Format.Format_RGB32)
    image.fill(0x007a455f)
    image_path = tmp_path / "appearance.png"
    assert image.save(str(image_path))

    settings = QSettings("Siegfridi", "Siegfridi")
    keys = (
        "appearance/theme",
        "appearance/background_path",
        "appearance/background_opacity",
        "appearance/background_fit",
        "appearance/background_protection",
        "theme",
        "background_path",
        "background_opacity",
        "background_fit",
        "background_protection",
    )
    previous = {key: settings.value(key) for key in keys if settings.contains(key)}
    for key in keys:
        settings.remove(key)
    # Legacy top-level keys must still be understood by a current build.
    settings.setValue("theme", "quiet-light")
    settings.setValue("background_path", str(image_path))
    settings.setValue("background_opacity", 0.31)
    settings.setValue("background_fit", "fit")
    settings.setValue("background_protection", 0.67)

    window = MainWindow(Project(tracks=[Track("Lead")]))
    reopened = None
    window_closed = False
    reopened_closed = False
    try:
        assert window._theme_id == "quiet-light"
        assert window.roll._theme_id == "quiet-light"
        assert window._backdrop._theme_id == "quiet-light"
        assert window._background_path == image_path.resolve()
        assert window._background_opacity == pytest.approx(0.31)
        assert window._background_fit == "fit"
        assert window._background_protection == pytest.approx(0.67)
        assert window.roll._background_fit == "fit"
        assert window.roll._background_protection == pytest.approx(0.67)

        window.set_theme("high-contrast")
        window.set_background_fit("cover")
        window.set_background_protection(0.52)
        window.set_background_opacity(0.24)
        window.close()
        window_closed = True
        qapp.processEvents()

        reopened = MainWindow(Project(tracks=[Track("Lead")]))
        assert reopened._theme_id == "high-contrast"
        assert reopened.roll._theme_id == "high-contrast"
        assert reopened._backdrop._theme_id == "high-contrast"
        assert reopened._background_path == image_path.resolve()
        assert reopened._background_fit == "cover"
        assert reopened._background_protection == pytest.approx(0.52)
        assert reopened._background_opacity == pytest.approx(0.24)
        assert reopened.roll._background_fit == "cover"

        reopened._reset_appearance()
        assert reopened._theme_id == "dark-gothic"
        assert reopened.roll._theme_id == "dark-gothic"
        assert reopened._backdrop._theme_id == "dark-gothic"
        assert reopened._background_path is None
        assert reopened._background_fit == "cover"
        assert reopened._background_opacity == pytest.approx(0.18)
        assert reopened._background_protection == pytest.approx(0.44)
        assert reopened.roll._background_pixmap.isNull()
    finally:
        if not window_closed:
            window.close()
        if reopened is not None and not reopened_closed:
            reopened.close()
        qapp.processEvents()
        for key in keys:
            settings.remove(key)
        for key, value in previous.items():
            settings.setValue(key, value)


def test_main_window_midi_device_connect_thru_and_disconnect(qapp: QApplication, monkeypatch) -> None:
    from PySide6.QtCore import QSettings

    settings = QSettings("Siegfridi", "Siegfridi")
    previous_name = settings.value("midi/input_name", None)
    settings.remove("midi/input_name")
    opened = []

    class FakeInput:
        name = "Test Keyboard"

        def __init__(self, mapping) -> None:
            self.mapping = mapping
            self.closed = False

        def set_mapping(self, mapping) -> None:
            self.mapping = mapping

        def close(self) -> None:
            self.closed = True

    def fake_open(name, _callback, mapping):
        assert name == "Test Keyboard"
        port = FakeInput(mapping)
        opened.append(port)
        return port

    monkeypatch.setattr("siegfridi.app.main_window.midi_input_names", lambda: ("Test Keyboard",))
    monkeypatch.setattr("siegfridi.app.main_window.open_midi_input", fake_open)
    sent = []

    class FakeOutput:
        def send(self, message) -> None:
            sent.append(message)

        def close(self) -> None:
            pass

    output = FakeOutput()
    monkeypatch.setattr("siegfridi.app.main_window.open_default_output", lambda: output)
    window = MainWindow(Project(tracks=[Track("Lead")]))
    try:
        window._midi_input_combo.setCurrentIndex(1)
        assert window._midi_input is opened[-1]
        window._midi_lowest_spin.setValue(36)
        assert opened[-1].mapping.lowest_note == 36

        window._midi_thru_check.setChecked(True)
        window._on_midi_event(MidiKeyboardEvent("note_on", 60, 60, 100, 2))
        assert sent[-1].type == "note_on"
        assert (2, 60) in window._midi_output_notes
        window._on_midi_event(MidiKeyboardEvent("note_off", 60, 60, 0, 2))
        assert sent[-1].type == "note_off"
        assert (2, 60) not in window._midi_output_notes

        # A held note is released when the input is disconnected/closed.
        window._on_midi_event(MidiKeyboardEvent("note_on", 61, 61, 100, 2))
        window._midi_input_combo.setCurrentIndex(0)
        assert opened[-1].closed
        assert sent[-1].type == "note_off" and sent[-1].note == 61
    finally:
        window.close()
        qapp.processEvents()
        if previous_name is None:
            settings.remove("midi/input_name")
        else:
            settings.setValue("midi/input_name", previous_name)


def test_main_window_midi_output_failure_is_reported(qapp: QApplication) -> None:
    class FailingOutput:
        def send(self, _message) -> None:
            raise RuntimeError("output gone")

    window = MainWindow(Project(tracks=[Track("Lead")]))
    window.player.set_output(FailingOutput())
    window._midi_thru_check.setChecked(True)
    window._on_midi_event(MidiKeyboardEvent("note_on", 60, 60, 100, 0))
    assert "disconnected" in window.statusBar().currentMessage()
    window._midi_output_notes.add((0, 60))
    window.close()
    qapp.processEvents()
    assert not window._midi_output_notes


def test_main_window_handles_midi_scan_and_open_failures(qapp: QApplication, monkeypatch) -> None:
    from PySide6.QtCore import QSettings

    settings = QSettings("Siegfridi", "Siegfridi")
    previous_name = settings.value("midi/input_name", None)
    settings.remove("midi/input_name")
    monkeypatch.setattr(
        "siegfridi.app.main_window.midi_input_names",
        lambda: (_ for _ in ()).throw(ValueError("backend missing")),
    )
    window = MainWindow(Project(tracks=[Track("Lead")]))
    try:
        assert window._midi_input_combo.count() == 1
        window._refresh_midi_inputs()
        assert "No MIDI input devices" in window.statusBar().currentMessage()

        monkeypatch.setattr("siegfridi.app.main_window.midi_input_names", lambda: ("Unavailable",))
        monkeypatch.setattr("siegfridi.app.main_window.open_midi_input", lambda *_args: None)
        window._refresh_midi_inputs()
        window._midi_input_combo.setCurrentIndex(1)
        assert "MIDI input unavailable" in window.statusBar().currentMessage()
    finally:
        window.close()
        qapp.processEvents()
        if previous_name is None:
            settings.remove("midi/input_name")
        else:
            settings.setValue("midi/input_name", previous_name)


def test_main_window_midi_mapping_and_recording_without_hardware(qapp: QApplication) -> None:
    project = Project(tracks=[Track("Lead")])
    window = MainWindow(project)
    window.show()
    qapp.processEvents()

    assert window._midi_input_combo.currentData() is None
    window._midi_thru_check.setChecked(False)
    window._midi_lowest_spin.setValue(36)
    window._midi_key_count_spin.setValue(49)
    window._midi_target_spin.setValue(48)
    assert window._midi_mapping.key_count == 49
    assert window._midi_mapping.map_note(36) == 48
    assert window._midi_mapping.map_note(85) is None

    window._midi_record_check.setChecked(True)
    window._on_midi_event(MidiKeyboardEvent("note_on", 52, 40, 96, 0))
    window._on_midi_event(MidiKeyboardEvent("note_off", 52, 40, 0, 0))
    assert project.tracks[0].notes == [Note(0, 1, 52, 96)]
    window._midi_record_check.setChecked(False)
    window.close()
    qapp.processEvents()


def test_main_window_native_project_save_open_and_mix_sync(qapp: QApplication, tmp_path: Path) -> None:
    project = Project(
        tempo_bpm=108,
        style_preset_id="dark-gothic",
        sound_pack_id="dark-gothic-v01",
        tracks=[Track("Organ", volume=0.8, pan=-0.25, notes=[Note(0, 480, 60)])],
    )
    window = MainWindow(project)
    window.show()
    qapp.processEvents()

    assert window.pack_combo.currentData().endswith("dark-gothic-v01.json")
    window._volume_spin.setValue(0.45)
    window._pan_spin.setValue(0.35)
    assert project.tracks[0].volume == 0.45
    assert project.tracks[0].pan == 0.35

    path = window.save_project(tmp_path / "workflow.siegfridi")
    assert path == tmp_path / "workflow.siegfridi"
    assert "*" not in window.windowTitle()
    project.tracks[0].volume = 0.1
    assert window.open_project(path) == path
    assert window.project.tracks[0].volume == 0.45
    assert window.project.tracks[0].pan == 0.35
    assert window._volume_spin.value() == 0.45
    assert window._pan_spin.value() == 0.35
    window.close()
    qapp.processEvents()


def test_action_triggered_boolean_does_not_become_project_path(
    qapp: QApplication, monkeypatch, tmp_path: Path
) -> None:
    window = MainWindow(Project(tracks=[Track("Lead")]))
    path = tmp_path / "action.siegfridi"
    window.save_project(path)
    monkeypatch.setattr(
        "siegfridi.app.main_window.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(path), ""),
    )
    assert window.save_project(False) == path
    monkeypatch.setattr(
        "siegfridi.app.main_window.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(path), ""),
    )
    assert window.open_project(False) == path
    window.close()
    qapp.processEvents()


def test_main_window_file_dialog_cancellation_is_reported(qapp: QApplication, monkeypatch) -> None:
    window = MainWindow(Project(tracks=[Track("Lead")]))
    monkeypatch.setattr(
        "siegfridi.app.main_window.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: ("", ""),
    )
    assert window.open_project() is None
    assert window.statusBar().currentMessage() == "Open cancelled"
    assert window.import_audio() is None
    assert window.statusBar().currentMessage() == "Audio import cancelled"
    monkeypatch.setattr(
        "siegfridi.app.main_window.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: ("", ""),
    )
    assert window.save_project() is None
    assert window.statusBar().currentMessage() == "Save cancelled"
    window.close()
    qapp.processEvents()


def test_main_window_transcription_start_and_poll_failures_are_recoverable(
    qapp: QApplication, monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "broken.wav"
    source.write_bytes(b"placeholder")

    class StartFailure:
        def __init__(self, _request) -> None:
            pass

        def start(self) -> None:
            raise RuntimeError("worker unavailable")

    monkeypatch.setattr("siegfridi.app.main_window.TranscriptionProcess", StartFailure)
    window = MainWindow(Project(tracks=[Track("Lead")]))
    window.import_audio(source)
    assert "Transcription failed" in window.statusBar().currentMessage()
    assert "worker unavailable" in window._candidate_info.text()
    assert window._import_button.isEnabled()
    assert not window._cancel_import_button.isEnabled()
    window.close()
    qapp.processEvents()


def test_main_window_transcription_poll_failure_restores_controls(
    qapp: QApplication, monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "poll-failure.wav"
    source.write_bytes(b"placeholder")

    class PollFailure:
        def __init__(self, request) -> None:
            self.request = request
            self.is_running = True
            self.closed = False

        def start(self) -> None:
            pass

        def poll(self) -> list[dict]:
            raise RuntimeError("queue closed")

        def close(self) -> None:
            self.closed = True

    process = None

    def make_process(request):
        nonlocal process
        process = PollFailure(request)
        return process

    monkeypatch.setattr("siegfridi.app.main_window.TranscriptionProcess", make_process)
    window = MainWindow(Project(tracks=[Track("Lead")]))
    window.import_audio(source)
    assert not window._import_button.isEnabled()
    window._poll_transcription()
    assert process is not None and process.closed
    assert window._transcription_process is None
    assert window._import_button.isEnabled()
    assert not window._cancel_import_button.isEnabled()
    assert not window._accept_button.isEnabled()
    assert "Transcription failed" in window.statusBar().currentMessage()
    window.close()
    qapp.processEvents()


def test_main_window_invalid_transcription_response_is_rejected(
    qapp: QApplication, monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "invalid-response.wav"
    source.write_bytes(b"placeholder")

    class InvalidResponse:
        def __init__(self, request) -> None:
            self.request = request
            self.is_running = True
            self.closed = False

        def start(self) -> None:
            pass

        def poll(self) -> list[object]:
            return ["not a message"]

        def close(self) -> None:
            self.closed = True

    process = None

    def make_process(request):
        nonlocal process
        process = InvalidResponse(request)
        return process

    monkeypatch.setattr("siegfridi.app.main_window.TranscriptionProcess", make_process)
    window = MainWindow(Project(tracks=[Track("Lead")]))
    window.import_audio(source)
    window._poll_transcription()
    assert process is not None and process.closed
    assert window._transcription_process is None
    assert window._import_button.isEnabled()
    assert not window._accept_button.isEnabled()
    assert "invalid worker response" in window._candidate_info.text()
    window.close()
    qapp.processEvents()


def test_main_window_playback_failure_is_reported(qapp: QApplication, monkeypatch) -> None:
    class FailingPlayer:
        output = None

        def start(self, _project) -> None:
            raise RuntimeError("audio backend unavailable")

        def stop(self) -> None:
            pass

    window = MainWindow(Project(tracks=[Track("Lead")]))
    window.player = FailingPlayer()
    monkeypatch.setattr("siegfridi.app.main_window.open_default_output", lambda: None)
    window._play()
    assert "Playback failed" in window.statusBar().currentMessage()
    assert not window._playback_timer.isActive()
    window.close()
    qapp.processEvents()


def test_main_window_transcription_candidate_review_and_cancel(qapp: QApplication, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "melody.wav"
    source.write_bytes(b"placeholder")
    result = TranscriptionResult(
        notes=(
            CandidateNote(0.0, 0.24, 60, 0.9, 100),
            CandidateNote(0.5, 1.0, 64, 0.2, 80),
        ),
        bpm=120,
        sample_rate=22050,
        source=str(source),
    )

    class FakeProcess:
        def __init__(self, request) -> None:
            self.request = request
            self.is_running = True
            self.cancelled = False
            self.closed = False

        def start(self) -> None:
            self.is_running = False

        def poll(self) -> list[dict]:
            return [{"type": "completed", "result": result}]

        def cancel(self) -> None:
            self.cancelled = True
            self.is_running = False

        def close(self) -> None:
            self.closed = True

    fake_processes: list[FakeProcess] = []

    def make_process(request):
        process = FakeProcess(request)
        fake_processes.append(process)
        return process

    monkeypatch.setattr("siegfridi.app.main_window.TranscriptionProcess", make_process)
    project = Project(tracks=[Track("Existing")])
    window = MainWindow(project)
    window.import_audio(source)
    window._poll_transcription()
    assert "1/2 candidates" in window._candidate_info.text()
    assert len(project.tracks) == 1
    window._confidence_spin.setValue(0.5)
    window._quantize_spin.setValue(120)
    window.accept_transcription()
    assert len(project.tracks) == 2
    assert project.tracks[-1].notes == [Note(0, 240, 60, 100)]

    window.import_audio(source)
    process = fake_processes[-1]
    window.cancel_transcription()
    assert process.cancelled is True
    assert "cancelled" in window._candidate_info.text()
    window.close()
    qapp.processEvents()
