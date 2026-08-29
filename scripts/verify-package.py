"""Verify a built Siegfridi onedir package before clean-machine handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REQUIRED_FILES = (
    "Siegfridi.exe",
    "_internal/THIRD_PARTY_NOTICES.md",
    "_internal/docs/README.md",
    "_internal/docs/QUICKSTART.md",
    "_internal/docs/VISUAL_CHECKLIST.md",
    "_internal/docs/requirements-lock-win-py311.txt",
    "_internal/docs/N6_RELEASE_HANDOFF.md",
    "_internal/assets/presets/example-dark-gothic.siegfridi",
    "_internal/assets/presets/example-oriental-project.siegfridi",
    "_internal/assets/presets/example-retro-rpg.siegfridi",
    "_internal/assets/packs/dark-gothic-v0.1.sf2",
    "_internal/assets/packs/dark-gothic-v01.json",
    "_internal/assets/packs/oriental-project-v0.1.sf2",
    "_internal/assets/packs/oriental-project-v01.json",
    "_internal/assets/packs/FluidR3_GM.sf2",
    "_internal/assets/packs/fluidr3-gm.json",
    "_internal/assets/packs/Ocarina-20241002.sf2",
    "_internal/assets/packs/freepats-ocarina.json",
    "_internal/fluidsynth.exe",
    "_internal/libfluidsynth-3.dll",
    "_internal/SDL3.dll",
    "_internal/sndfile.dll",
)
DISALLOWED_SUFFIXES = {".sfz", ".wav", ".flac", ".mp3", ".ogg"}
DISALLOWED_MARKERS = ("local-study-only", "THFont", "NeoTHFont", "ZUNpet", "Touhou.sf2")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package(root: Path, expected_version: str | None = None) -> dict[str, object]:
    root = root.resolve()
    manifest_path = root / "package-manifest.json"
    if not root.is_dir() or not manifest_path.is_file():
        raise ValueError(f"not a packaged Siegfridi directory: {root}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read package manifest: {manifest_path}") from exc
    if payload.get("application") != "siegfridi" or payload.get("schema_version") != 1:
        raise ValueError("unsupported package manifest")
    records = payload.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("package manifest has no files")

    expected_paths = {str(record.get("path")) for record in records if isinstance(record, dict)}
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "package-manifest.json"
    }
    missing_records = actual_paths - expected_paths
    if missing_records:
        raise ValueError(f"files missing from package manifest: {sorted(missing_records)[:5]}")
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("package manifest contains an invalid record")
        relative = record.get("path")
        path = root / str(relative)
        if not path.is_file() or path.stat().st_size != record.get("size") or _digest(path) != record.get("sha256"):
            raise ValueError(f"package hash mismatch: {relative}")

    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise ValueError(f"required package files are missing: {missing}")
    forbidden = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name == "package-manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in DISALLOWED_SUFFIXES or any(marker in relative for marker in DISALLOWED_MARKERS):
            forbidden.append(relative)
    if forbidden:
        raise ValueError(f"non-redistributable files found in package: {forbidden[:5]}")

    if expected_version is not None:
        executable = root / "Siegfridi.exe"
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0 or completed.stdout.strip() != expected_version:
            raise ValueError(
                f"packaged executable version mismatch: {completed.stdout.strip()!r}"
            )

    return {
        "application": "siegfridi",
        "package_root": str(root),
        "file_count": len(records),
        "package_bytes": sum(int(record["size"]) for record in records),
        "required_files": list(REQUIRED_FILES),
        "expected_version": expected_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="built application directory")
    parser.add_argument("--version", default=None, help="version expected by the release handoff")
    parser.add_argument("--report", type=Path, default=None, help="optional JSON report path")
    args = parser.parse_args()
    report = verify_package(args.root, args.version)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified package: {report['file_count']} files, {report['package_bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
