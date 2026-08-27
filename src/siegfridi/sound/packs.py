"""Versioned SoundFont pack manifests and integrity checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profiles import SoundProfile


class SoundPackError(RuntimeError):
    """Raised when a SoundFont pack is missing or fails validation."""


@dataclass(frozen=True, slots=True)
class SoundPackManifest:
    id: str
    name: str
    version: str
    soundfont: str
    sha256: str
    license: str
    profiles: tuple[SoundProfile, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.name or not self.version:
            raise ValueError("sound pack id, name and version must not be empty")
        if Path(self.soundfont).suffix.lower() not in {".sf2", ".sf3"}:
            raise ValueError("soundfont must be an .sf2 or .sf3 file")
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256.lower()):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        if not self.license:
            raise ValueError("license must not be empty")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SoundPackManifest:
        profiles = tuple(SoundProfile(**profile) for profile in payload.get("profiles", ()))
        return cls(
            id=str(payload["id"]),
            name=str(payload["name"]),
            version=str(payload["version"]),
            soundfont=str(payload["soundfont"]),
            sha256=str(payload["sha256"]).lower(),
            license=str(payload["license"]),
            profiles=profiles,
        )

    @classmethod
    def load(cls, path: str | Path) -> SoundPackManifest:
        manifest_path = Path(path)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SoundPackError(f"could not read sound pack manifest: {manifest_path}") from exc
        if not isinstance(payload, dict):
            raise SoundPackError("sound pack manifest must contain a JSON object")
        try:
            return cls.from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise SoundPackError(f"invalid sound pack manifest: {manifest_path}") from exc

    def resolve_soundfont(self, manifest_path: str | Path) -> Path:
        """Resolve the manifest's relative SoundFont path next to the manifest."""
        path = Path(manifest_path).resolve().parent / self.soundfont
        if not path.is_file():
            raise SoundPackError(f"SoundFont file does not exist: {path}")
        return path

    def verify(self, manifest_path: str | Path) -> Path:
        """Resolve and hash-check the SoundFont file before playback/rendering."""
        path = self.resolve_soundfont(manifest_path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != self.sha256:
            raise SoundPackError(
                f"SoundFont hash mismatch for {path}: expected {self.sha256}, got {digest}"
            )
        return path


def load_sound_pack(path: str | Path) -> SoundPackManifest:
    """Convenience wrapper for loading a JSON manifest."""
    return SoundPackManifest.load(path)
