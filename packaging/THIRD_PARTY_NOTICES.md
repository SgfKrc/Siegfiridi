# Third-party notices

The distribution is built from the pinned project dependencies. Before a
release, copy the exact license texts and source URLs for every wheel and
native binary into this directory and include the resulting files in the
installer.

The current runtime boundary includes:

- PySide6 / Qt, LGPL-3.0/GPL-2.0-or-later with Qt exceptions as applicable.
- Mido, MIT.
- python-rtmidi and RtMidi, MIT.
- PyAV and FFmpeg, BSD-3-Clause / LGPL or GPL depending on the FFmpeg build.
- librosa, scipy, soundfile and NumPy, permissive licenses documented by each
  upstream distribution.
- Basic Pitch and TensorFlow, Apache-2.0.
- FluidSynth and pyFluidSynth, LGPL-2.1-or-later.

SoundFonts, models and recorded samples are separate assets. They must not be
bundled unless their redistribution license, source and SHA-256 are recorded
in the corresponding asset manifest.

Current asset records:

- FluidR3_GM 3.1: MIT, runtime fallback; see `assets/packs/fluidr3-gm.json` and
  `assets/packs/FluidR3_GM.COPYING`.
- SP Bamboo Flute source commit `bffe30a67a29c8b2dc691e1a45af78b801d57ce6`:
  CC0-1.0, SFZ/WAV authoring source only; see
  `assets/packs/sp-bamboo-flute-source.json` and the copied `LICENSE` under
  `assets/packs/sources/sp-bamboo-flute/`. It is not a runtime pack and is not
  collected by the PyInstaller spec.
- FreePats Ocarina 2024-10-02: CC0-1.0, runtime SF2 candidate; see
  `assets/packs/freepats-ocarina.json`, `assets/packs/FreePats-Ocarina.CC0.txt`
  and `assets/packs/FreePats-Ocarina.SOURCE.txt`.
