import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def _load_verifier():
    source = Path(__file__).parents[1] / "scripts" / "verify-package.py"
    spec = importlib.util.spec_from_file_location("siegfridi_verify_package", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package(tmp_path: Path, *, forbidden: str | None = None) -> Path:
    root = tmp_path / "Siegfridi"
    required = _load_verifier().REQUIRED_FILES
    for relative in required:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    if forbidden:
        path = root / forbidden
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"forbidden")
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    (root / "package-manifest.json").write_text(
        json.dumps({"schema_version": 1, "application": "siegfridi", "files": records}),
        encoding="utf-8",
    )
    return root


def test_verify_package_checks_required_files_and_hashes(tmp_path: Path) -> None:
    verifier = _load_verifier()
    report = verifier.verify_package(_package(tmp_path))
    assert report["file_count"] == len(verifier.REQUIRED_FILES)


def test_verify_package_rejects_non_redistributable_assets(tmp_path: Path) -> None:
    verifier = _load_verifier()
    with pytest.raises(ValueError, match="non-redistributable"):
        verifier.verify_package(_package(tmp_path, forbidden="assets/packs/local-study-only.sf2"))


def test_verify_package_rejects_hash_changes(tmp_path: Path) -> None:
    verifier = _load_verifier()
    root = _package(tmp_path)
    (root / "_internal/docs/README.md").write_bytes(b"changed")
    with pytest.raises(ValueError, match="package hash mismatch"):
        verifier.verify_package(root)
