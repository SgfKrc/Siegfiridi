"""Extract a pinned 7z asset archive for the PowerShell fetch scripts."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import py7zr


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: extract-7z.py ARCHIVE EXTRACT_DIR PACK_DIR")
    archive_path = Path(sys.argv[1])
    extract_dir = Path(sys.argv[2])
    pack_dir = Path(sys.argv[3])
    extract_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extractall(path=extract_dir)

    soundfonts = list(extract_dir.rglob("*.sf2"))
    if len(soundfonts) != 1:
        raise SystemExit(f"expected one SF2 in archive, found {len(soundfonts)}")
    shutil.copy2(soundfonts[0], pack_dir / "Ocarina-20241002.sf2")
    for filename, target in (
        ("LICENSE.txt", "FreePats-Ocarina.CC0.txt"),
        ("README.txt", "FreePats-Ocarina.SOURCE.txt"),
    ):
        matches = list(extract_dir.rglob(filename))
        if len(matches) != 1:
            raise SystemExit(f"expected one {filename} in archive, found {len(matches)}")
        shutil.copy2(matches[0], pack_dir / target)


if __name__ == "__main__":
    main()
