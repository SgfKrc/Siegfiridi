import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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

    window.close()
    app.processEvents()
