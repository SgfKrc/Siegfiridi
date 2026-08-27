"""Dependency-free configuration models for custom sound packs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SoundProfile:
    """Maps a track role to a SoundFont program and optional articulation data."""

    id: str
    name: str
    soundfont_path: str | None = None
    bank: int = 0
    program: int = 0
    key_switches: dict[str, int] = field(default_factory=dict)
    octave_offset: int = 0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id must not be empty")
        if not 0 <= self.bank <= 16383:
            raise ValueError("bank must be between 0 and 16383")
        if not 0 <= self.program <= 127:
            raise ValueError("program must be between 0 and 127")


@dataclass(frozen=True, slots=True)
class StylePreset:
    """A reusable style recipe independent from note events."""

    id: str
    name: str
    tempo_min: float = 80.0
    tempo_max: float = 160.0
    meters: tuple[str, ...] = ("4/4",)
    default_roles: tuple[str, ...] = ()
    sound_profile_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id must not be empty")
        if self.tempo_min <= 0 or self.tempo_max < self.tempo_min:
            raise ValueError("tempo range is invalid")
