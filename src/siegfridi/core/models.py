"""Small, dependency-free musical model for the first vertical slice."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Note:
    """A note event stored in integer ticks."""

    start_tick: int
    duration_tick: int
    pitch: int
    velocity: int = 100

    def __post_init__(self) -> None:
        if self.start_tick < 0:
            raise ValueError("start_tick must be non-negative")
        if self.duration_tick <= 0:
            raise ValueError("duration_tick must be positive")
        if not 0 <= self.pitch <= 127:
            raise ValueError("pitch must be between 0 and 127")
        if not 1 <= self.velocity <= 127:
            raise ValueError("velocity must be between 1 and 127")

    @property
    def end_tick(self) -> int:
        return self.start_tick + self.duration_tick

    def quantized(self, grid_tick: int) -> Note:
        """Return a note with start and end snapped to a positive grid."""
        if grid_tick <= 0:
            raise ValueError("grid_tick must be positive")
        start = round(self.start_tick / grid_tick) * grid_tick
        end = max(start + grid_tick, round(self.end_tick / grid_tick) * grid_tick)
        return Note(start, end - start, self.pitch, self.velocity)


@dataclass(slots=True)
class Track:
    name: str
    role: str = "custom"
    notes: list[Note] = field(default_factory=list)
    muted: bool = False
    solo: bool = False
    volume: float = 1.0
    pan: float = 0.0
    sound_profile_id: str | None = None


@dataclass(slots=True)
class Project:
    """Project state shared by the editor, playback and export layers."""

    ppq: int = 480
    tempo_bpm: float = 120.0
    tracks: list[Track] = field(default_factory=list)
    style_preset_id: str | None = None

    def __post_init__(self) -> None:
        if self.ppq <= 0:
            raise ValueError("ppq must be positive")
        if self.tempo_bpm <= 0:
            raise ValueError("tempo_bpm must be positive")

    def quantized(self, grid_tick: int) -> Project:
        """Return a copy with all track notes snapped to the requested grid."""
        return Project(
            ppq=self.ppq,
            tempo_bpm=self.tempo_bpm,
            style_preset_id=self.style_preset_id,
            tracks=[
                Track(
                    name=track.name,
                    role=track.role,
                    notes=[note.quantized(grid_tick) for note in track.notes],
                    muted=track.muted,
                    solo=track.solo,
                    volume=track.volume,
                    pan=track.pan,
                    sound_profile_id=track.sound_profile_id,
                )
                for track in self.tracks
            ],
        )
