# CodeBuddy roadmap

**Stage: prototype** · next: alpha, when the MVP success criteria in SPEC.md are 6/6

> **Last reviewed:** 2026-10-14 · **Last updated:** 2026-10-14 · **Change:** minor (G6 proactive hints done: criteria 5/6) · **Target:** SPEC.md MVP, then module checklists + eval score

## Headline numbers

| | Value | Kind |
|---|---|---|
| MVP success criteria met | 5/6 (2 proactive, 3 token budget, 4 trigger rules, 5 demo, 6 gate); 1 latency p50 open | measured: see devlog 2026-10-14 21:50 |
| `#?` first-token latency, `buddy ask` → Claude CLI (~1k tokens in) | p50 2.9 s, range 1.6–5.8 s (target p50 ≤ 3 s, at risk) | measured: 15 runs on 2026-10-14 (devlog) |
| Proactive hint, idle → hint done (Qwen3-Coder-30B-A3B, llama.cpp) | 585 ms (first token 24 ms); idle fires 4.05 s after the last keystroke | measured: 1 live run on 2026-10-14 (devlog) |
| Tests (brain / notch / plugin) | 116 / 40 / 26 | measured: `python3 scripts/ratchet.py` |
| Eval score of suggestions | — | not defined yet (G10) |

## By dimension

| Dimension | % ready | Estimate | Doc |
|---|---:|---:|---|
| Protocol | 100% of v0 | measured: 9/9 types with examples | protocol/README.md |
| Brain | ~70% | estimated: G2 and G6 done; latency (G5) and evals (G10) open | G5, G10 |
| Notch UI | ~75% | estimated: G3 done, hint peek with preview; real-screen check (G11) and Sprout design (G8) open | G8, G11 |
| PyCharm plugin | ~80% | estimated: G4 and idle events (G6) done; real-IDE use (G13) open | G13 |
| Growth (skill map, exercises, curriculum, diary) | 0% | not started, after MVP | CAPABILITY-MAP.md |

## Next

1. **MVP**: G13 (Human) → G5 latency p50 (G1–G4 and G6 done).
2. **Evals** (G10) so suggestion quality becomes a number.
3. **Growth** module, then `#!alt`, `#!review`, the priority queue and the study/work toggle.
