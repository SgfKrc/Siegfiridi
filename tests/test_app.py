import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import siegfridi.__main__ as entrypoint
from siegfridi.app.main_window import MainWindow, _runtime_pack_paths


def test_runtime_pack_discovery_excludes_source_only_manifest() -> None:
    paths = _runtime_pack_paths()

    assert any(path.name == "fluidr3-gm.json" for path in paths)
    assert any(path.name == "freepats-ocarina.json" for path in paths)
    assert all(path.name != "sp-bamboo-flute-source.json" for path in paths)


def test_main_window_exposes_style_pack_and_preview_controls() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.style_combo.count() >= 3
    assert window.style_combo.currentData() == "dark-gothic"
    assert window.pack_combo.count() >= 2
    assert window.render_button.isEnabled()
    assert "tracks" in window._project_info.text()
    assert not window.roll.selection_mode
    window._selection_mode_button.click()
    assert window.roll.selection_mode
    assert window.roll.viewport().cursor().shape().name == "CrossCursor"
    window._selection_mode_button.click()
    assert not window.roll.selection_mode

    window.close()
    app.processEvents()


def test_cli_entrypoint_delegates_to_launcher(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["siegfridi"])
    monkeypatch.setattr("siegfridi.app.main_window.launch", lambda: 23)
    assert entrypoint.main() == 23


def test_cli_entrypoint_version_action_exits_cleanly(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["siegfridi", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        entrypoint.main()
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "0.1.0"
