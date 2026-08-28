"""Generate the N7 visual baseline set and check Qt layout bounds."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import siegfridi.app.main_window as main_window_module
from siegfridi.app.main_window import MainWindow

SCENARIOS = (
    ("dark-gothic-desktop", "dark-gothic", 1440, 900),
    ("quiet-light-desktop", "quiet-light", 1440, 900),
    ("high-contrast-narrow", "high-contrast", 900, 700),
)


def _rect_inside(child: QWidget, parent: QWidget) -> bool:
    top_left = child.mapTo(parent, QPoint(0, 0))
    bottom_right = child.mapTo(parent, child.rect().bottomRight())
    return parent.rect().contains(top_left) and parent.rect().contains(bottom_right)


def _layout_check(window: MainWindow) -> list[str]:
    central = window.centralWidget()
    workspace = window._control_scroll.parentWidget()
    errors: list[str] = []
    if central is None or not _rect_inside(central, window):
        errors.append("central widget is outside the window")
    if workspace is None:
        errors.append("workbench workspace is missing")
    else:
        for name, widget in (("control scroll", window._control_scroll), ("piano roll", window.roll)):
            if not _rect_inside(widget, workspace):
                errors.append(f"{name} is outside the workspace")
            if widget.width() <= 0 or widget.height() <= 0:
                errors.append(f"{name} has no visible area")
    if window._control_scroll.horizontalScrollBar().isVisible():
        errors.append("control scroll unexpectedly has a horizontal scrollbar")
    return errors


def _capture(window: MainWindow, output: Path) -> dict[str, object]:
    pixmap = window.grab()
    if pixmap.isNull() or not pixmap.save(str(output)):
        raise RuntimeError(f"could not save screenshot: {output}")
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    dpr = pixmap.devicePixelRatio()
    expected_size = (round(window.width() * dpr), round(window.height() * dpr))
    if (image.width(), image.height()) != expected_size:
        raise RuntimeError(
            f"unexpected screenshot size for {output}: "
            f"got {image.width()}x{image.height()}, expected {expected_size[0]}x{expected_size[1]}"
        )
    samples = {
        image.pixelColor(x, y).rgba()
        for x in range(0, image.width(), max(1, image.width() // 8))
        for y in range(0, image.height(), max(1, image.height() // 8))
    }
    if len(samples) < 4:
        raise RuntimeError(f"screenshot appears blank: {output}")
    status = window.statusBar().currentMessage()
    if "no MIDI output device" not in status:
        raise RuntimeError(f"no-audio fallback status missing for {output}: {status}")
    return {
        "output": str(output),
        "logical_size": [window.width(), window.height()],
        "physical_size": [image.width(), image.height()],
        "device_pixel_ratio": dpr,
        "font_family_count": len(QFontDatabase.families()),
        "status": status,
        "control_scroll": [
            window._control_scroll.x(),
            window._control_scroll.y(),
            window._control_scroll.width(),
            window._control_scroll.height(),
        ],
        "piano_roll": [window.roll.x(), window.roll.y(), window.roll.width(), window.roll.height()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".siegfridi/visual/n7-005"))
    parser.add_argument(
        "--scale-factor",
        type=float,
        default=None,
        help="Set QT_SCALE_FACTOR before QApplication for a high-DPI run",
    )
    args = parser.parse_args()
    if args.scale_factor is not None:
        if args.scale_factor <= 0:
            parser.error("scale factor must be positive")
        os.environ["QT_SCALE_FACTOR"] = str(args.scale_factor)

    # Keep the baseline deterministic and exercise the no-hardware status path.
    main_window_module.open_default_output = lambda: None
    app = QApplication.instance() or QApplication([])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, object]] = []
    for slug, theme, width, height in SCENARIOS:
        window = MainWindow()
        window.resize(width, height)
        window.set_theme(theme, persist=False)
        window.set_background_image(None, persist=False)
        window.set_background_opacity(0.18, persist=False)
        window.set_background_fit("cover", persist=False)
        window.set_background_protection(0.44, persist=False)
        window.show()
        app.processEvents()
        # The worker thread has no required output device; its status is part of
        # the baseline to ensure the no-audio fallback remains visible.
        window._play()
        app.processEvents()
        errors = _layout_check(window)
        if errors:
            window._stop_playback()
            window.close()
            raise RuntimeError(f"{slug}: {'; '.join(errors)}")
        metadata = _capture(window, args.output_dir / f"{slug}.png")
        metadata.update({"scenario": slug, "theme": theme, "requested_size": [width, height]})
        report.append(metadata)
        window._stop_playback()
        window.close()
        app.processEvents()

    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Checked {len(report)} GUI scenarios; report: {report_path}")
    for item in report:
        print(
            f"- {item['scenario']}: {item['logical_size'][0]}x{item['logical_size'][1]}, "
            f"DPR {item['device_pixel_ratio']}, status={item['status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
