# CodeBuddy roadmap

**Stage: prototype** · next: alpha, when the MVP success criteria in SPEC.md are 6/6

> **Last reviewed:** 2026-10-14 · **Last updated:** 2026-10-14 · **Change:** minor (G3 notch app done) · **Target:** SPEC.md MVP, then module checklists + eval score

## Headline numbers

| | Value | Kind |
|---|---|---|
| MVP success criteria met | 0/6 | measured: by hand against SPEC.md → Success criteria |
| `#?` first-token latency, `buddy ask` → Claude CLI (~1k tokens in) | p50 2.9 s, range 1.6–5.8 s (target p50 ≤ 3 s, at risk) | measured: 15 runs on 2026-10-14 (devlog) |
| Tests (brain / notch / plugin) | 81 / 36 / 0 | measured: `python3 scripts/ratchet.py` |
| Eval score of suggestions | — | not defined yet (G10) |

## By dimension

| Dimension | % ready | Estimate | Doc |
|---|---:|---:|---|
| Protocol | 100% of v0 | measured: 9/9 types with examples | protocol/README.md |
| Brain | ~50% | estimated: G2 done, G6 (proactive) open | G6 |
| Notch UI | ~70% | estimated: G3 done; real-screen check (G11) and Sprout design (G8) open | G8, G11 |
| PyCharm plugin | 0% | estimated | G4 |
| Growth (skill map, exercises, curriculum, diary) | 0% | not started, after MVP | CAPABILITY-MAP.md |

## Next

1. **MVP**: G4 → G5 → G6 (G1, G2, G3 done).
2. **Evals** (G10) so suggestion quality becomes a number.
3. **Growth** module, then `#!alt`, `#!review`, the priority queue and the study/work toggle.
