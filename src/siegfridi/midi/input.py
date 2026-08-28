"""MIDI keyboard input and compact-controller range mapping."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import mido


@dataclass(frozen=True, slots=True)
class MidiKeyboardMapping:
    """Map a device's physical key range into the standard 0-127 MIDI range.

    MIDI controllers report note numbers rather than a key index, but compact
    25/49/61/76/88-key devices often start at a non-zero note.  ``lowest_note``
    and ``key_count`` describe that physical range; ``target_lowest_note``
    allows the same keyboard to be used as a transposed input surface.
    """

    lowest_note: int = 0
    key_count: int = 128
    target_lowest_note: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.lowest_note <= 127:
            raise ValueError("lowest_note must be between 0 and 127")
        if not 1 <= self.key_count <= 128:
            raise ValueError("key_count must be between 1 and 128")
        if self.lowest_note + self.key_count > 128:
            raise ValueError("lowest_note + key_count must not exceed 128")
        if not 0 <= self.target_lowest_note <= 127:
            raise ValueError("target_lowest_note must be between 0 and 127")
        if self.target_lowest_note + self.key_count > 128:
            raise ValueError("target_lowest_note + key_count must not exceed 128")

    def map_note(self, note: int) -> int | None:
        """Return the mapped note, or ``None`` for an out-of-range key."""
        if not 0 <= note <= 127:
            return None
        key_index = note - self.lowest_note
        if not 0 <= key_index < self.key_count:
            return None
        return self.target_lowest_note + key_index


@dataclass(frozen=True, slots=True)
class MidiKeyboardEvent:
    """A validated note event emitted by :class:`MidiKeyboardInput`."""

    kind: str
    note: int
    source_note: int
    velocity: int
    channel: int

    def to_message(self) -> mido.Message:
        if self.kind == "note_on":
            return mido.Message(
                "note_on",
                channel=self.channel,
                note=self.note,
                velocity=self.velocity,
            )
        return mido.Message("note_off", channel=self.channel, note=self.note, velocity=0)


def midi_input_names() -> tuple[str, ...]:
    """Return available MIDI input names without making startup hardware-dependent."""
    try:
        return tuple(mido.get_input_names())
    except (OSError, RuntimeError, ValueError):
        return ()


class MidiKeyboardInput:
    """Callback-driven input port with safe note-range mapping."""

    def __init__(
        self,
        port,
        callback: Callable[[MidiKeyboardEvent], None],
        mapping: MidiKeyboardMapping | None = None,
    ) -> None:
        self._port = port
        self._callback = callback
        self._mapping = mapping or MidiKeyboardMapping()
        self._active: dict[tuple[int, int], int] = {}

    @property
    def name(self) -> str:
        return str(getattr(self._port, "name", "MIDI input"))

    @property
    def mapping(self) -> MidiKeyboardMapping:
        return self._mapping

    @property
    def is_open(self) -> bool:
        return not bool(getattr(self._port, "closed", False))

    def set_mapping(self, mapping: MidiKeyboardMapping) -> None:
        self._mapping = mapping

    def handle_message(self, message: mido.Message) -> None:
        """Process one message; public for deterministic tests and adapters."""
        if message.type not in {"note_on", "note_off"}:
            return
        source_note = int(message.note)
        key = (int(getattr(message, "channel", 0)), source_note)
        is_on = message.type == "note_on" and int(message.velocity) > 0
        if is_on:
            mapped_note = self._mapping.map_note(source_note)
            if mapped_note is None:
                return
            self._active[key] = mapped_note
            event = MidiKeyboardEvent(
                "note_on",
                mapped_note,
                source_note,
                max(1, min(127, int(message.velocity))),
                key[0],
            )
        else:
            mapped_note = self._active.pop(key, self._mapping.map_note(source_note))
            if mapped_note is None:
                return
            event = MidiKeyboardEvent("note_off", mapped_note, source_note, 0, key[0])
        self._callback(event)

    def close(self) -> None:
        """Close the port and forget held notes so a later port cannot leak them."""
        try:
            self._port.callback = None
        except (AttributeError, OSError, RuntimeError, ValueError):
            pass
        close = getattr(self._port, "close", None)
        if close is not None:
            try:
                close()
            except (OSError, RuntimeError, ValueError):
                pass
        self._active.clear()


def open_midi_input(
    name: str,
    callback: Callable[[MidiKeyboardEvent], None],
    mapping: MidiKeyboardMapping | None = None,
) -> MidiKeyboardInput | None:
    """Open a named input using Mido's callback thread, returning ``None`` on failure."""
    if not name:
        return None
    try:
        port = mido.open_input(name)
    except (OSError, RuntimeError, ValueError):
        return None
    input_port = MidiKeyboardInput(port, callback, mapping)
    # Mido callback ports expose a callback attribute; assigning it after
    # wrapping keeps the wrapper testable with simple fake ports.
    try:
        port.callback = input_port.handle_message
    except (AttributeError, RuntimeError, ValueError):
        input_port.close()
        return None
    return input_port
