"""Versioned serialization for native ``.siegfridi`` project files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import Note, Project, Track

FORMAT = "siegfridi-project"
SCHEMA_VERSION = 1


class ProjectFileError(ValueError):
    """Raised when a native project file is missing or invalid."""


def _note_to_dict(note: Note) -> dict[str, int]:
    return {
        "start_tick": note.start_tick,
        "duration_tick": note.duration_tick,
        "pitch": note.pitch,
        "velocity": note.velocity,
    }


def project_to_dict(project: Project) -> dict[str, Any]:
    """Return a JSON-compatible snapshot of all editable project state."""
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "ppq": project.ppq,
        "tempo_bpm": project.tempo_bpm,
        "style_preset_id": project.style_preset_id,
        "sound_pack_id": project.sound_pack_id,
        "tracks": [
            {
                "name": track.name,
                "role": track.role,
                "muted": track.muted,
                "solo": track.solo,
                "volume": track.volume,
                "pan": track.pan,
                "sound_profile_id": track.sound_profile_id,
                "notes": [_note_to_dict(note) for note in track.notes],
            }
            for track in project.tracks
        ],
    }


def _required(payload: dict[str, Any], key: str) -> Any:
    try:
        return payload[key]
    except KeyError as exc:
        raise ProjectFileError(f"project field is missing: {key}") from exc


def _note_from_dict(payload: Any) -> Note:
    if not isinstance(payload, dict):
        raise ProjectFileError("note must be a JSON object")
    try:
        return Note(
            start_tick=int(_required(payload, "start_tick")),
            duration_tick=int(_required(payload, "duration_tick")),
            pitch=int(_required(payload, "pitch")),
            velocity=int(payload.get("velocity", 100)),
        )
    except (TypeError, ValueError, ProjectFileError) as exc:
        raise ProjectFileError("invalid note data") from exc


def project_from_dict(payload: Any) -> Project:
    """Validate and decode a native project payload."""
    if not isinstance(payload, dict):
        raise ProjectFileError("project file must contain a JSON object")
    if payload.get("format") != FORMAT:
        raise ProjectFileError("unsupported project format")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ProjectFileError("unsupported project schema version")
    tracks_payload = payload.get("tracks", [])
    if not isinstance(tracks_payload, list):
        raise ProjectFileError("tracks must be a JSON array")
    tracks: list[Track] = []
    try:
        for item in tracks_payload:
            if not isinstance(item, dict):
                raise ProjectFileError("track must be a JSON object")
            raw_notes = item.get("notes", [])
            if not isinstance(raw_notes, list):
                raise ProjectFileError("track notes must be a JSON array")
            profile_id = item.get("sound_profile_id")
            if profile_id is not None and not isinstance(profile_id, str):
                raise ProjectFileError("sound_profile_id must be a string or null")
            tracks.append(
                Track(
                    name=str(_required(item, "name")),
                    role=str(item.get("role", "custom")),
                    muted=bool(item.get("muted", False)),
                    solo=bool(item.get("solo", False)),
                    volume=float(item.get("volume", 1.0)),
                    pan=float(item.get("pan", 0.0)),
                    sound_profile_id=profile_id,
                    notes=[_note_from_dict(note) for note in raw_notes],
                )
            )
        return Project(
            ppq=int(_required(payload, "ppq")),
            tempo_bpm=float(_required(payload, "tempo_bpm")),
            style_preset_id=payload.get("style_preset_id"),
            sound_pack_id=payload.get("sound_pack_id"),
            tracks=tracks,
        )
    except (TypeError, ValueError, ProjectFileError) as exc:
        if isinstance(exc, ProjectFileError):
            raise
        raise ProjectFileError("invalid project data") from exc


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def save_siegfridi(project: Project, path: str | Path, *, backup: bool = True) -> Path:
    """Atomically save a native project and keep the previous file as ``.bak``."""
    destination = Path(path)
    if destination.suffix.lower() != ".siegfridi":
        raise ProjectFileError("native project path must use the .siegfridi suffix")
    if backup and destination.is_file():
        destination.replace(destination.with_suffix(destination.suffix + ".bak"))
    text = json.dumps(project_to_dict(project), ensure_ascii=False, indent=2) + "\n"
    try:
        _atomic_write(destination, text)
    except BaseException:
        backup_path = destination.with_suffix(destination.suffix + ".bak")
        if not destination.exists() and backup_path.exists():
            backup_path.replace(destination)
        raise
    return destination


def load_siegfridi(path: str | Path) -> Project:
    """Load and validate a native project file."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectFileError(f"could not read project file: {source}") from exc
    return project_from_dict(payload)


def autosave_project(project: Project, directory: str | Path) -> Path:
    """Write the crash-recovery snapshot without rotating the user's backup."""
    directory_path = Path(directory)
    return save_siegfridi(project, directory_path / "autosave.siegfridi", backup=False)
