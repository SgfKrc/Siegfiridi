"""PyInstaller entry point that preserves the siegfridi package context."""

from siegfridi.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
