"""Build a small, original CC0 SoundFont for the Oriental Project palette.

The generated samples are deterministic procedural waveforms.  No Touhou,
Roland, game, or third-party recordings are embedded in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

SAMPLE_RATE = 22_050
ROOT_KEY = 60


def _chunk(identifier: bytes, payload: bytes) -> bytes:
    padding = b"\0" if len(payload) % 2 else b""
    return identifier + struct.pack("<I", len(payload)) + payload + padding


def _list_chunk(identifier: bytes, payload: bytes) -> bytes:
    return _chunk(b"LIST", identifier + payload)


def _text_chunk(identifier: bytes, text: str) -> bytes:
    payload = text.encode("utf-8") + b"\0"
    # FluidSynth is strict about even-sized INFO chunks, although RIFF's
    # padding byte normally sits outside the declared chunk size.
    if len(payload) % 2:
        payload += b"\0"
    return _chunk(identifier, payload)


def _envelope(position: float, attack: float, release: float) -> float:
    if position < attack:
        return position / attack
    if position > 1.0 - release:
        return max(0.0, (1.0 - position) / release)
    return 1.0


def _sample(kind: str, duration: float = 1.5) -> list[int]:
    count = round(SAMPLE_RATE * duration)
    values: list[int] = []
    phase = 0.0
    seed = 0x51E6F1
    for index in range(count):
        t = index / SAMPLE_RATE
        position = t / duration
        if kind == "brass":
            frequency = 261.6256 * (1.0 + 0.004 * math.sin(2.0 * math.pi * 5.2 * t))
            phase += 2.0 * math.pi * frequency / SAMPLE_RATE
            signal = (
                0.58 * math.sin(phase)
                + 0.26 * math.sin(2.0 * phase)
                + 0.12 * math.sin(3.0 * phase)
                + 0.06 * math.sin(5.0 * phase)
            )
            amplitude = _envelope(position, 0.018, 0.08)
        elif kind == "fm":
            carrier = 2.0 * math.pi * 261.6256 * t
            modulator = 2.0 * math.pi * 523.2511 * t
            signal = math.sin(carrier + 2.7 * math.sin(modulator))
            amplitude = _envelope(position, 0.004, 0.12)
        elif kind == "wind":
            phase += 2.0 * math.pi * 261.6256 / SAMPLE_RATE
            seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
            breath = ((seed >> 16) / 32767.5) - 1.0
            signal = 0.78 * math.sin(phase) + 0.12 * math.sin(2.0 * phase) + 0.08 * breath
            amplitude = _envelope(position, 0.05, 0.18)
        elif kind == "percussion":
            seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
            noise = ((seed >> 16) / 32767.5) - 1.0
            signal = 0.65 * noise + 0.35 * math.sin(2.0 * math.pi * 90.0 * t)
            amplitude = max(0.0, 1.0 - position) ** 3
        elif kind == "bass":
            frequency = 65.4064 * (1.0 + 0.002 * math.sin(2.0 * math.pi * 3.1 * t))
            phase += 2.0 * math.pi * frequency / SAMPLE_RATE
            signal = 0.62 * math.sin(phase) + 0.24 * math.sin(2.0 * phase) + 0.14 * math.sin(3.0 * phase)
            amplitude = _envelope(position, 0.012, 0.1)
        else:
            raise ValueError(f"unknown sample kind: {kind}")
        values.append(max(-32767, min(32767, round(signal * amplitude * 0.72 * 32767))))
    return values


def _pack_records(records: list[bytes], terminal: bytes) -> bytes:
    return b"".join(records) + terminal


def _fixed_text(text: str, size: int) -> bytes:
    return text.encode("ascii", errors="replace")[: size - 1].ljust(size, b"\0")


def _build_sf2(samples: dict[str, list[int]]) -> bytes:
    sample_names = tuple(samples)
    sample_data: list[int] = []
    headers: list[tuple[str, int, int, int, int]] = []
    for name in sample_names:
        values = samples[name]
        start = len(sample_data)
        sample_data.extend(values)
        end = len(sample_data)
        # Keep a short release-safe loop; the final 46 samples are the SF2
        # guard samples required by the format and are outside this loop.
        loop_start = start + min(2_000, max(0, len(values) // 5))
        loop_end = end - min(2_000, max(0, len(values) // 5))
        headers.append((name, start, end, loop_start, loop_end))
        sample_data.extend([0] * 46)

    smpl = struct.pack(f"<{len(sample_data)}h", *sample_data)
    info = _chunk(b"ifil", struct.pack("<HH", 2, 1))
    info += _text_chunk(b"isng", "EMU8000")
    info += _text_chunk(b"INAM", "Siegfridi Oriental Project Palette")

    shdr_records: list[bytes] = []
    for name, start, end, loop_start, loop_end in headers:
        shdr_records.append(
            struct.pack(
                "<20sIIIIIBbHH",
                _fixed_text(name, 20),
                start,
                end,
                loop_start,
                loop_end,
                SAMPLE_RATE,
                ROOT_KEY,
                0,
                0,
                1,
            )
        )
    shdr_records.append(struct.pack("<20sIIIIIBbHH", _fixed_text("EOS", 20), len(sample_data), len(sample_data), len(sample_data), len(sample_data), SAMPLE_RATE, 0, 0, 0, 1))

    instrument_names = tuple(f"{name.title()} Instrument" for name in sample_names)
    igen_records: list[bytes] = []
    ibag_records: list[bytes] = []
    for sample_index, _name in enumerate(sample_names):
        generator_start = len(igen_records)
        igen_records.extend(
            (
                struct.pack("<HH", 43, 0x7F00),  # keyRange 0..127
                struct.pack("<HH", 54, 1),  # looping sample mode
                struct.pack("<HH", 58, ROOT_KEY),
                struct.pack("<HH", 53, sample_index),
            )
        )
        ibag_records.append(struct.pack("<HH", generator_start, 0))
    ibag_records.append(struct.pack("<HH", len(igen_records), 0))
    inst_records = [struct.pack("<20sH", _fixed_text(name, 20), index) for index, name in enumerate(instrument_names)]
    inst_records.append(struct.pack("<20sH", _fixed_text("EOI", 20), len(ibag_records) - 1))

    pgen_records = [struct.pack("<HH", 41, index) for index in range(len(sample_names))]
    pbag_records = [struct.pack("<HH", index, 0) for index in range(len(pgen_records))]
    pbag_records.append(struct.pack("<HH", len(pgen_records), 0))
    preset_names = ("Oriental Brass", "FM Lead", "Breathy Wind", "Chip Percussion", "FM Bass")
    programs = (56, 80, 73, 0, 33)
    phdr_records = [
        struct.pack("<20sHHHIII", _fixed_text(name, 20), program, 0, index, 0, 0, 0)
        for index, (name, program) in enumerate(zip(preset_names, programs, strict=True))
    ]
    phdr_records.append(struct.pack("<20sHHHIII", _fixed_text("EOP", 20), 0, 0, len(pbag_records) - 1, 0, 0, 0))

    zero_mod = struct.pack("<HHhHH", 0, 0, 0, 0, 0)
    pdta = _chunk(b"phdr", _pack_records(phdr_records, b""))
    pdta += _chunk(b"pbag", _pack_records(pbag_records, b""))
    pdta += _chunk(b"pmod", zero_mod)
    pdta += _chunk(b"pgen", _pack_records(pgen_records, b""))
    pdta += _chunk(b"inst", _pack_records(inst_records, b""))
    pdta += _chunk(b"ibag", _pack_records(ibag_records, b""))
    pdta += _chunk(b"imod", zero_mod)
    pdta += _chunk(b"igen", _pack_records(igen_records, b""))
    pdta += _chunk(b"shdr", _pack_records(shdr_records, b""))
    root = _list_chunk(b"INFO", info) + _list_chunk(b"sdta", _chunk(b"smpl", smpl)) + _list_chunk(b"pdta", pdta)
    return _chunk(b"RIFF", b"sfbk" + root)


def build(output: Path, manifest_path: Path) -> None:
    samples = {
        "brass": _sample("brass"),
        "fm": _sample("fm"),
        "wind": _sample("wind"),
        "percussion": _sample("percussion"),
        "bass": _sample("bass"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_build_sf2(samples))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "id": "oriental-project-v01",
        "name": "Siegfridi Oriental Project Palette",
        "version": "0.1.0",
        "soundfont": output.name,
        "sha256": digest,
        "license": "CC0-1.0",
        "source_url": "https://github.com/SgfKrc/Siegfiridi",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": "Original deterministic procedural samples generated by scripts/build-oriental-pack.py.",
        "category": "project-original",
        "distribution": "redistributable",
        "notes": "ZUN-style feature reconstruction only; contains no Touhou, Roland, game, or third-party samples.",
        "profiles": [
            {"id": "zunpet-trumpet", "name": "Original brass attack", "program": 56},
            {"id": "lead-synth", "name": "Original FM lead", "program": 80},
            {"id": "fm-lead", "name": "Original FM lead", "program": 80},
            {"id": "chip-square", "name": "Original FM/chip lead", "program": 80},
            {"id": "folk-wind", "name": "Original breathy wind", "program": 73},
            {"id": "electric-bass", "name": "Original FM bass", "program": 33},
            {"id": "sampled-drums", "name": "Original chip percussion", "program": 0},
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("assets/packs/oriental-project-v0.1.sf2"))
    parser.add_argument("--manifest", type=Path, default=Path("assets/packs/oriental-project-v01.json"))
    args = parser.parse_args()
    build(args.output, args.manifest)
    print(f"Generated {args.output} ({args.output.stat().st_size} bytes)")
    print(f"Manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
