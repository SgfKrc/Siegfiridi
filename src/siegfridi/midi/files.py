"""MIDI file adapters for the first vertical slice."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

import mido

from ..core.models import Note, Project, Track
from ..sound.profiles import SoundProfile

_METADATA_PREFIX = "siegfridi:"


def _track_metadata(track: Track) -> str:
    payload = {
        "role": track.role,
        "sound_profile_id": track.sound_profile_id,
    }
    return _METADATA_PREFIX + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _read_track_metadata(text: str) -> tuple[str, str | None] | None:
    if not text.startswith(_METADATA_PREFIX):
        return None
    try:
        payload = json.loads(text[len(_METADATA_PREFIX) :])
    except json.JSONDecodeError:
        return None
    role = payload.get("role", "custom")
    profile_id = payload.get("sound_profile_id")
    if not isinstance(role, str) or not isinstance(profile_id, (str, type(None))):
        return None
    return role, profile_id


def _note_messages(track: Track) -> Iterable[tuple[int, int, mido.Message]]:
    """Yield absolute-tick note messages, with note-offs before note-ons at ties."""
    for note in track.notes:
        yield note.start_tick, 1, mido.Message("note_on", note=note.pitch, velocity=note.velocity)
        yield note.end_tick, 0, mido.Message("note_off", note=note.pitch, velocity=0)


def project_to_midi(
    project: Project,
    profile_lookup: Mapping[str, SoundProfile] | None = None,
) -> mido.MidiFile:
    """Convert a project into a type-1 Standard MIDI File in memory."""
    midi = mido.MidiFile(type=1, ticks_per_beat=project.ppq)

    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("track_name", name="Siegfridi Tempo"))
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(project.tempo_bpm), time=0))
    midi.tracks.append(tempo_track)

    for track in project.tracks:
        midi_track = mido.MidiTrack()
        midi_track.append(mido.MetaMessage("track_name", name=track.name, time=0))
        midi_track.append(mido.MetaMessage("text", text=_track_metadata(track), time=0))

        profile = profile_lookup.get(track.sound_profile_id) if profile_lookup and track.sound_profile_id else None
        if profile is not None:
            bank_msb, bank_lsb = divmod(profile.bank, 128)
            if bank_msb:
                midi_track.append(mido.Message("control_change", control=0, value=bank_msb, time=0))
            if bank_lsb:
                midi_track.append(mido.Message("control_change", control=32, value=bank_lsb, time=0))
            midi_track.append(mido.Message("program_change", program=profile.program, time=0))
        if track.volume != 1.0:
            midi_track.append(
                mido.Message("control_change", control=7, value=round(track.volume * 127), time=0)
            )
        if track.pan != 0.0:
            midi_track.append(
                mido.Message(
                    "control_change",
                    control=10,
                    value=round((track.pan + 1.0) * 63.5),
                    time=0,
                )
            )

        events = sorted(_note_messages(track), key=lambda item: (item[0], item[1]))
        last_tick = 0
        for tick, _, message in events:
            message.time = tick - last_tick
            midi_track.append(message)
            last_tick = tick
        midi_track.append(mido.MetaMessage("end_of_track", time=0))
        midi.tracks.append(midi_track)

    return midi


def save_project(
    project: Project,
    path: str | Path,
    profile_lookup: Mapping[str, SoundProfile] | None = None,
) -> None:
    """Write a project as a Standard MIDI File."""
    project_to_midi(project, profile_lookup).save(str(path))


def midi_to_project(midi: mido.MidiFile) -> Project:
    """Convert a MIDI file into the dependency-free project model."""
    tempo_bpm = 120.0
    tempo_found = False
    tracks: list[Track] = []

    for index, midi_track in enumerate(midi.tracks):
        absolute_tick = 0
        track_name = f"Track {index + 1}"
        role = "custom"
        profile_id: str | None = None
        volume = 1.0
        pan = 0.0
        open_notes: dict[tuple[int, int], list[tuple[int, int]]] = {}
        notes: list[Note] = []

        for message in midi_track:
            absolute_tick += int(message.time)
            if message.is_meta:
                if message.type == "set_tempo" and not tempo_found:
                    tempo_bpm = mido.tempo2bpm(message.tempo)
                    tempo_found = True
                elif message.type == "track_name":
                    track_name = message.name
                elif message.type == "text":
                    metadata = _read_track_metadata(message.text)
                    if metadata is not None:
                        role, profile_id = metadata
                continue

            if message.type == "note_on" and message.velocity > 0:
                key = (message.channel, message.note)
                open_notes.setdefault(key, []).append((absolute_tick, message.velocity))
            elif message.type in {"note_off", "note_on"}:
                key = (message.channel, message.note)
                pending = open_notes.get(key)
                if pending:
                    start_tick, velocity = pending.pop(0)
                    if absolute_tick > start_tick:
                        notes.append(
                            Note(
                                start_tick=start_tick,
                                duration_tick=absolute_tick - start_tick,
                                pitch=message.note,
                                velocity=velocity,
                            )
                        )
                    if not pending:
                        open_notes.pop(key, None)
            elif message.type == "control_change":
                if message.control == 7:
                    volume = message.value / 127.0
                elif message.control == 10:
                    pan = message.value / 63.5 - 1.0

        # A malformed file may omit note-offs. Do not create unbounded notes.
        # Use the actual MIDI track end as the fallback boundary for notes
        # without a matching note-off; otherwise a later dangling note can
        # be silently truncated to the last already-closed note.
        track_end = max(absolute_tick, max((note.end_tick for note in notes), default=0))
        for (_, pitch), pending in open_notes.items():
            for start_tick, velocity in pending:
                if track_end > start_tick:
                    notes.append(
                        Note(
                            start_tick=start_tick,
                            duration_tick=track_end - start_tick,
                            pitch=pitch,
                            velocity=velocity,
                        )
                    )

        if notes or index > 0:
            tracks.append(
                Track(
                    name=track_name,
                    role=role,
                    notes=sorted(notes, key=lambda note: (note.start_tick, note.pitch)),
                    volume=volume,
                    pan=pan,
                    sound_profile_id=profile_id,
                )
            )

    return Project(ppq=midi.ticks_per_beat, tempo_bpm=tempo_bpm, tracks=tracks)


def load_project(path: str | Path) -> Project:
    """Read a Standard MIDI File into the project model."""
    return midi_to_project(mido.MidiFile(str(path)))
