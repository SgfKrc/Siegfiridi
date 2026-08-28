"""Write a deterministic hash manifest for a built application directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_record(root: Path, path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": digest,
    }


def write_manifest(root: Path, destination: Path) -> Path:
    files = [file_record(root, path) for path in sorted(root.rglob("*")) if path.is_file()]
    payload = {
        "schema_version": 1,
        "application": "siegfridi",
        "files": files,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="built application directory")
    parser.add_argument("output", type=Path, help="manifest JSON path")
    args = parser.parse_args()
    write_manifest(args.root.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
