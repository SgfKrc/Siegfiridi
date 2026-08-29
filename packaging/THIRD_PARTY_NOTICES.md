# Third-party notices

The distribution is built from the pinned project dependencies. The N6 release
bundle includes this notice, the dependency lock snapshot at
`docs/requirements-lock-win-py311.txt`, every collected `*.dist-info` license
file, and the asset manifests/license texts under `assets/packs/`. The final
`package-manifest.json` records a SHA-256 for each of those files. This notice
summarizes the runtime boundary; it does not replace the upstream license
terms shipped with the package.

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
- Siegfridi Oriental Project Palette 0.1.0: CC0-1.0 original procedural
  project asset; see `assets/packs/oriental-project-v01.json`,
  `assets/packs/OrientalProjectPalette.CC0.txt` and
  `assets/packs/OrientalProjectPalette.SOURCE.txt`.
- Siegfridi Dark Gothic Palette 0.1.0: CC0-1.0 original procedural project
  asset; see `assets/packs/dark-gothic-v01.json`,
  `assets/packs/DarkGothicPalette.CC0.txt` and
  `assets/packs/DarkGothicPalette.SOURCE.txt`.

The bundled native FluidSynth runtime is the Windows build discovered from
`SIEGFRIDI_FLUIDSYNTH_DIR` (or `C:\\tools\\fluidsynth\\bin` on the build
machine). Its DLLs remain separate files so that a recipient can replace them
with a compatible build while retaining the corresponding upstream notices.

The locally cached THFont, NeoTHFont, ZUNpet, PC-98 and SRX reference packs
are marked `local-study-only` and are intentionally excluded from PyInstaller
data collection. They remain governed by their individual NOTICE files and
are not project distribution assets.
