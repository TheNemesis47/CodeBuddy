# Installer art

Made on 2026-10-16 with Draw Things (HTTP API on :7860, FLUX.2 Klein 9B, 10 steps, guidance 4,
one image each), then composed by `packaging/make_art.py` (text, arrow, the light card under the
dmg icons, transparent icon corners). The raw images (`raw/`) are not committed; to redo one,
generate it again with the prompt below and run `uv run --project overlay python
packaging/make_art.py`.

| File | From | Prompt (seed) |
|---|---|---|
| `icon.png` (1024²) | `raw/icon.png` 1024² | macOS app icon, rounded square squircle, centered: a cute small green seedling sprouting from a round brown seed that has two tiny friendly dot eyes, two fresh leaves, the seed sits on a dark charcoal background with a soft green glow, subtle code brackets { } faintly etched in the background, clean flat vector style with gentle soft shading, professional app icon, no text, no letters (4242) |
| `dmg-background.png`, `@2x`, `wizard.png` | `raw/scene.png` 1536×1024 | wide calm background illustration, dark night garden seen from low angle, a few small glowing green seedlings sprouting from dark soil along the bottom edge, soft bokeh fireflies, deep charcoal and dark green tones, large empty dark space in the upper and middle area, minimal, flat vector illustration with soft gradients, no text, no letters (777) |

The icon is a stand-in for Sprout's final design, which is the human's (docs/gaps.md G8).
