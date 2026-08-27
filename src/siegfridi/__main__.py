"""Command-line entry point for the desktop application."""

from __future__ import annotations

import argparse

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(prog="siegfridi")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()

    try:
        from .app.main_window import launch
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            parser.error("PySide6 未安装，请运行 python -m pip install -e '.[dev]'")
        raise

    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
