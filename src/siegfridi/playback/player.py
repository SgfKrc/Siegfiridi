"""Timing and output adapters for the first MIDI playback slice."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, Self

import mido

from ..core.models import Project


class MessageSink(Protocol):
    """Minimal output contract, also convenient for tests."""

    def send(self, message: mido.Message) -> None: ...


@dataclass(frozen=True, slots=True)
class ScheduledEvent:
    tick: int
    track_index: int
    message: mido.Message


def tick_to_seconds(tick: int, ppq: int, tempo_bpm: float) -> float:
    """Convert project ticks to seconds using the project's constant tempo."""
    if tick < 0:
        raise ValueError("tick must be non-negative")
    if ppq <= 0 or tempo_bpm <= 0:
        raise ValueError("ppq and tempo_bpm must be positive")
    return tick * 60.0 / (ppq * tempo_bpm)


def scheduled_events(project: Project, start_tick: int = 0) -> list[ScheduledEvent]:
    """Build a stable, globally ordered MIDI timeline from a project."""
    if start_tick < 0:
        raise ValueError("start_tick must be non-negative")
    has_solo = any(track.solo for track in project.tracks)
    events: list[ScheduledEvent] = []
    for track_index, track in enumerate(project.tracks):
        if track.muted or (has_solo and not track.solo):
            continue
        channel = track_index % 16
        for note in track.notes:
            if note.end_tick <= start_tick:
                continue
            start = max(note.start_tick, start_tick)
            events.append(
                ScheduledEvent(
                    start,
                    track_index,
                    mido.Message("note_on", channel=channel, note=note.pitch, velocity=note.velocity),
                )
            )
            events.append(
                ScheduledEvent(
                    note.end_tick,
                    track_index,
                    mido.Message("note_off", channel=channel, note=note.pitch, velocity=0),
                )
            )
    # note_off precedes note_on at the same tick to avoid stuck/retrigger ambiguity.
    events.sort(key=lambda item: (item.tick, item.message.type == "note_on", item.track_index))
    return events


class _SendCallable:
    def __init__(self, callback: Callable[[mido.Message], None]) -> None:
        self._callback = callback

    def send(self, message: mido.Message) -> None:
        self._callback(message)


def midi_output_names() -> tuple[str, ...]:
    """Return available output names without making startup depend on RtMidi."""
    try:
        return tuple(mido.get_output_names())
    except (OSError, RuntimeError, ValueError):
        return ()


def open_default_output(name: str | None = None) -> MessageSink | None:
    """Open a requested output, or the first system MIDI output when available."""
    output_name = name
    if output_name is None:
        output_name = next(iter(midi_output_names()), None)
    if output_name is None:
        return None
    try:
        return mido.open_output(output_name)
    except (OSError, RuntimeError, ValueError):
        return None


class MidiPlayer:
    """A cancellable background player with no required hardware output."""

    def __init__(
        self,
        output: MessageSink | Callable[[mido.Message], None] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._output = _SendCallable(output) if callable(output) else output
        self._sleeper = sleeper
        self._interruptible_sleep = sleeper is time.sleep
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._resume.set()
        self._thread: threading.Thread | None = None
        self._active: set[tuple[int, int]] = set()
        self._position_tick = 0

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def output(self) -> MessageSink | None:
        return self._output

    @property
    def position_tick(self) -> int:
        """Current playback cursor in project ticks."""
        return self._position_tick

    @property
    def is_paused(self) -> bool:
        return self.is_playing and not self._resume.is_set()

    def set_output(self, output: MessageSink | Callable[[mido.Message], None] | None) -> None:
        self._output = _SendCallable(output) if callable(output) else output

    def _send(self, message: mido.Message) -> None:
        if self._output is not None:
            self._output.send(message)

    def _wait_for_resume(self) -> bool:
        while not self._stop.is_set():
            if self._resume.wait(0.02):
                return True
        return False

    def _sleep_for(self, seconds: float) -> bool:
        if not self._interruptible_sleep:
            self._sleeper(seconds)
            return not self._stop.is_set()
        remaining = max(0.0, seconds)
        while not self._stop.is_set():
            if not self._wait_for_resume():
                return False
            if remaining <= 0:
                return True
            started = time.monotonic()
            if self._stop.wait(min(remaining, 0.02)):
                return False
            remaining -= time.monotonic() - started
        return False

    def _send_track_controls(self, project: Project) -> None:
        has_solo = any(track.solo for track in project.tracks)
        for track_index, track in enumerate(project.tracks):
            if track.muted or (has_solo and not track.solo):
                continue
            channel = track_index % 16
            if track.volume != 1.0:
                self._send(
                    mido.Message("control_change", channel=channel, control=7, value=round(track.volume * 127))
                )
            if track.pan != 0.0:
                self._send(
                    mido.Message(
                        "control_change",
                        channel=channel,
                        control=10,
                        value=round((track.pan + 1.0) * 63.5),
                    )
                )

    def play_blocking(self, project: Project, start_tick: int = 0) -> None:
        """Play a project on the calling thread; useful for deterministic tests."""
        previous_seconds = tick_to_seconds(start_tick, project.ppq, project.tempo_bpm)
        self._active.clear()
        self._stop.clear()
        self._resume.set()
        self._position_tick = start_tick
        try:
            self._send_track_controls(project)
            for event in scheduled_events(project, start_tick):
                if not self._wait_for_resume():
                    break
                event_seconds = tick_to_seconds(event.tick, project.ppq, project.tempo_bpm)
                if not self._sleep_for(max(0.0, event_seconds - previous_seconds)):
                    break
                self._send(event.message)
                self._position_tick = event.tick
                key = (event.message.channel, event.message.note)
                if event.message.type == "note_on" and event.message.velocity:
                    self._active.add(key)
                else:
                    self._active.discard(key)
                previous_seconds = event_seconds
        finally:
            self._all_notes_off()

    def start(self, project: Project, start_tick: int = 0) -> None:
        self.stop()
        self._stop.clear()
        self._resume.set()
        self._thread = threading.Thread(
            target=self.play_blocking,
            args=(project, start_tick),
            name="siegfridi-midi-player",
            daemon=True,
        )
        self._thread.start()

    def pause(self) -> None:
        """Pause a running player while retaining its current tick cursor."""
        if self.is_playing:
            self._resume.clear()
            self._all_notes_off()

    def resume(self) -> None:
        """Resume a paused player."""
        self._resume.set()

    def seek(self, tick: int) -> None:
        """Move the cursor; an active playback is stopped before seeking."""
        if tick < 0:
            raise ValueError("tick must be non-negative")
        was_playing = self.is_playing
        if was_playing:
            self.stop()
        self._position_tick = tick

    def stop(self) -> None:
        self._stop.set()
        self._resume.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None
        self._all_notes_off()
        self._position_tick = 0

    def _all_notes_off(self) -> None:
        for channel, note in tuple(self._active):
            self._send(mido.Message("note_off", channel=channel, note=note, velocity=0))
        self._active.clear()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
