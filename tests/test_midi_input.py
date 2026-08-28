from types import SimpleNamespace

import mido
import pytest

from siegfridi.midi import (
    MidiKeyboardEvent,
    MidiKeyboardInput,
    MidiKeyboardMapping,
    midi_input_names,
    open_midi_input,
)


class _FakePort:
    def __init__(self, name: str = "Controller") -> None:
        self.name = name
        self.closed = False
        self.callback = None

    def close(self) -> None:
        self.closed = True


def test_compact_keyboard_mapping_accepts_non_three_digit_key_counts() -> None:
    mapping = MidiKeyboardMapping(lowest_note=36, key_count=49, target_lowest_note=48)

    assert mapping.map_note(36) == 48
    assert mapping.map_note(84) == 96
    assert mapping.map_note(35) is None
    assert mapping.map_note(85) is None

    with pytest.raises(ValueError):
        MidiKeyboardMapping(lowest_note=100, key_count=49)
    with pytest.raises(ValueError):
        MidiKeyboardMapping(key_count=0)
    with pytest.raises(ValueError):
        MidiKeyboardMapping(lowest_note=127, key_count=2)
    with pytest.raises(ValueError):
        MidiKeyboardMapping(target_lowest_note=127, key_count=2)


def test_mapping_and_event_conversion_cover_midi_boundaries() -> None:
    mapping = MidiKeyboardMapping(lowest_note=1, key_count=2, target_lowest_note=126)
    assert mapping.map_note(-1) is None
    assert mapping.map_note(0) is None
    assert mapping.map_note(1) == 126
    assert mapping.map_note(2) == 127
    assert mapping.map_note(3) is None
    assert mapping.map_note(128) is None

    note_on = MidiKeyboardEvent("note_on", 64, 60, 99, 3).to_message()
    note_off = MidiKeyboardEvent("note_off", 64, 60, 0, 3).to_message()
    assert note_on.type == "note_on"
    assert note_on.note == 64 and note_on.velocity == 99 and note_on.channel == 3
    assert note_off.type == "note_off"
    assert note_off.note == 64 and note_off.velocity == 0 and note_off.channel == 3


def test_input_preserves_note_off_mapping_when_range_changes() -> None:
    port = _FakePort()
    events = []
    keyboard = MidiKeyboardInput(port, events.append, MidiKeyboardMapping(36, 49, 48))

    keyboard.handle_message(mido.Message("note_on", note=40, velocity=100, channel=2))
    keyboard.set_mapping(MidiKeyboardMapping(0, 128, 0))
    keyboard.handle_message(mido.Message("note_off", note=40, velocity=0, channel=2))

    assert [(event.kind, event.note, event.source_note, event.channel) for event in events] == [
        ("note_on", 52, 40, 2),
        ("note_off", 52, 40, 2),
    ]
    keyboard.close()
    assert port.closed


def test_input_ignores_other_messages_and_handles_velocity_zero() -> None:
    port = _FakePort()
    events = []
    keyboard = MidiKeyboardInput(port, events.append, MidiKeyboardMapping(60, 1, 72))

    keyboard.handle_message(mido.Message("control_change", control=1, value=127))
    keyboard.handle_message(mido.Message("note_on", note=59, velocity=100))
    keyboard.handle_message(mido.Message("note_on", note=60, velocity=0))
    assert [(event.kind, event.note) for event in events] == [("note_off", 72)]

    # Mido validates normal messages, so use a minimal adapter to cover the
    # defensive velocity clamp used for third-party port implementations.
    keyboard.handle_message(SimpleNamespace(type="note_on", note=60, velocity=200, channel=0))
    assert events[-1].velocity == 127
    assert keyboard.name == "Controller"
    assert keyboard.is_open


def test_input_close_tolerates_port_shutdown_races() -> None:
    class FragilePort:
        name = "Fragile"
        closed = False

        @property
        def callback(self):
            return None

        @callback.setter
        def callback(self, _value):
            raise RuntimeError("port already gone")

        def close(self) -> None:
            raise OSError("port already gone")

    keyboard = MidiKeyboardInput(FragilePort(), lambda _event: None)
    keyboard.close()
    assert keyboard.is_open


def test_input_enumeration_and_open_failures_are_safe(monkeypatch) -> None:
    monkeypatch.setattr(mido, "get_input_names", lambda: ["Keyboard", "Pad"])
    assert midi_input_names() == ("Keyboard", "Pad")
    monkeypatch.setattr(mido, "get_input_names", lambda: (_ for _ in ()).throw(OSError("missing")))
    assert midi_input_names() == ()
    monkeypatch.setattr(mido, "get_input_names", lambda: (_ for _ in ()).throw(ValueError("unsupported")))
    assert midi_input_names() == ()

    port = _FakePort("Keyboard")
    monkeypatch.setattr(mido, "open_input", lambda _name: port)
    events = []
    keyboard = open_midi_input("Keyboard", events.append)
    assert keyboard is not None
    assert port.callback is not None
    port.callback(mido.Message("note_on", note=60, velocity=90))
    assert events[0].note == 60
    keyboard.close()

    monkeypatch.setattr(mido, "open_input", lambda _name: (_ for _ in ()).throw(RuntimeError("gone")))
    assert open_midi_input("Keyboard", events.append) is None

    monkeypatch.setattr(mido, "open_input", lambda _name: (_ for _ in ()).throw(ValueError("unsupported")))
    assert open_midi_input("Keyboard", events.append) is None
    assert open_midi_input("", events.append) is None


def test_open_input_closes_port_when_callback_binding_fails(monkeypatch) -> None:
    class NoCallbackPort:
        name = "No callback"
        closed = False

        @property
        def callback(self):
            return None

        @callback.setter
        def callback(self, _value):
                raise RuntimeError("callback unsupported")

        def close(self) -> None:
            self.closed = True

    port = NoCallbackPort()
    monkeypatch.setattr(mido, "open_input", lambda _name: port)
    assert open_midi_input("Keyboard", lambda _event: None) is None
    assert port.closed
