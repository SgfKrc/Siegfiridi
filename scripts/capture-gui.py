"""Capture the Qt workbench for repeatable offscreen visual inspection."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from siegfridi.app.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".siegfridi/visual/main-window.png"))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument(
        "--theme",
        choices=("dark-gothic", "high-contrast", "quiet-light"),
        default=None,
        help="Optional UI theme preset",
    )
    parser.add_argument("--background", type=Path, help="Optional local image to preview as the workbench background")
    parser.add_argument(
        "--background-opacity",
        type=float,
        default=None,
        help="Optional background image opacity from 0.0 to 1.0",
    )
    parser.add_argument(
        "--background-fit",
        choices=("cover", "fit"),
        default=None,
        help="Optional background image fit mode",
    )
    parser.add_argument(
        "--background-protection",
        type=float,
        default=None,
        help="Optional readability overlay strength from 0.0 to 1.0",
    )
    args = parser.parse_args()
    if args.width < 320 or args.height < 240:
        parser.error("width must be >= 320 and height must be >= 240")

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(args.width, args.height)
    if args.theme is not None:
        window.set_theme(args.theme, persist=False)
    if args.background is not None and not window.set_background_image(args.background, persist=False):
        raise RuntimeError(f"could not load background image: {args.background}")
    if args.background_opacity is not None:
        window.set_background_opacity(args.background_opacity, persist=False)
    if args.background_fit is not None:
        window.set_background_fit(args.background_fit, persist=False)
    if args.background_protection is not None:
        window.set_background_protection(args.background_protection, persist=False)
    window.show()
    app.processEvents()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(args.output)):
        raise RuntimeError(f"could not save screenshot: {args.output}")
    print(f"Captured {args.output} ({args.width}x{args.height})")
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
