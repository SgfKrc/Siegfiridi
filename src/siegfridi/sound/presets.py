"""Built-in style recipes for the project's custom music direction."""

from __future__ import annotations

from .profiles import StylePreset

BUILTIN_STYLE_PRESETS: tuple[StylePreset, ...] = (
    StylePreset(
        id="oriental-project",
        name="Oriental Project",
        tempo_min=135,
        tempo_max=190,
        meters=("4/4", "3/4", "6/8"),
        default_roles=("melody", "counter_melody", "bass", "drums"),
        sound_profile_ids=("lead-synth", "folk-wind", "electric-bass"),
    ),
    StylePreset(
        id="dark-gothic",
        name="Dark Gothic",
        tempo_min=70,
        tempo_max=150,
        meters=("4/4", "6/8", "12/8"),
        default_roles=("organ", "choir", "strings", "bass"),
        sound_profile_ids=(
            "cathedral-organ",
            "dark-choir",
            "bell",
            "bowed-bass",
            "plucked-relic",
            "gothic-percussion",
        ),
    ),
    StylePreset(
        id="retro-rpg",
        name="Retro RPG",
        tempo_min=90,
        tempo_max=175,
        meters=("4/4", "3/4", "6/8"),
        default_roles=("fm-lead", "chip-arpeggio", "bass", "drums"),
        sound_profile_ids=("fm-lead", "chip-square", "sampled-drums"),
    ),
)


def get_style_preset(style_id: str) -> StylePreset:
    """Return a built-in style or raise a useful lookup error."""
    for preset in BUILTIN_STYLE_PRESETS:
        if preset.id == style_id:
            return preset
    raise KeyError(f"unknown style preset: {style_id}")
