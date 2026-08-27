"""Minimal desktop shell used during project bootstrap."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from .. import __version__


class MainWindow(QMainWindow):
    """Initial shell; editor panels will be added behind this stable entry point."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Siegfridi {__version__}")
        self.resize(1100, 700)
        label = QLabel("Siegfridi\n定制化 MIDI 音轨工作台正在初始化")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)


def launch() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
