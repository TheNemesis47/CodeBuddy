# CodeBuddy roadmap

**Stage: prototype** · next: alpha, when the MVP success criteria in SPEC.md are 6/6

> **Last reviewed:** 2026-10-16 · **Last updated:** 2026-10-16 · **Change:** minor, 0.2.0 (one model for everything; review on Ctrl+S; panel opens at the first token; trigger line erased once sent; deep `#!teoria` + `#!approfondisci`; installers: dmg, Setup.exe, AppImage) · **Target:** SPEC.md MVP, then module checklists + eval score

## Headline numbers

| | Value | Kind |
|---|---|---|
| MVP success criteria met | 6/6 (1 latency p50, 2 proactive, 3 token budget, 4 trigger rules, 5 demo, 6 gate) | measured: devlog 2026-10-15 10:10 (criterion 1) and 2026-10-14 21:50 |
| `#?` first-token latency, plugin code path → brain → Claude Sonnet 5.5 → notch (1.7–3.2k tokens in) | p50 1572 ms, p90 1896 ms, range 1397–2097 ms (target p50 ≤ 3 s: met); repeat run p50 1634 ms, range 1492–2967 ms | measured: `scripts/bench-latency`, 2 × 10 runs on 2026-10-15 (devlog) |
| Proactive hint, idle → hint done (Qwen3-Coder-30B-A3B, llama.cpp) | 585 ms (first token 24 ms); idle fires 4.05 s after the last keystroke | measured: 1 live run on 2026-10-14 (devlog) |
| Tests (brain / notch / plugin / overlay) | 283 / 47 / 60 / 121 | measured: `python3 scripts/ratchet.py` (2026-10-16) |
| Theory depth (5 `#!teoria` cases, Claude Sonnet 5.5) | 100.0 (an `--only` run: not the ratcheted total) | measured: `buddy eval --triggers --only t-…`, 2026-10-16 (devlog) |
| CI (`.github/workflows/ci.yml`) | green on ubuntu, windows, macos + Linux e2e + packaged-build e2e on Linux and Windows | measured: run 38710592165, 2026-10-15 |
| Eval score of suggestions (29 cases, deterministic checks, 0–100) | **99.1** (baseline 94.5); judge 3.89/5 (local, not ratcheted) | measured: `buddy eval --repeat 3 --triggers --judge local`, `evals/results/2026-10-15-2.json`; hints Qwen3-Coder-30B-A3B on llama.cpp, triggers Sonnet 5.5 |

## By dimension

| Dimension | % ready | Estimate | Doc |
|---|---:|---:|---|
| Protocol | 100% of v0 | measured: 9/9 types with examples | protocol/README.md |
| Brain | ~80% | estimated: G2, G5 (latency log + `buddy latency`), G6 and G10 (evals + scorer) done | G14 |
| Linux/Windows | ~70% | estimated: overlay (same states and scenarios as the notch), portable brain, packages and CI on 3 OSes done; real-machine tries, code signing and the first release are human (G15) | G15 |
| Notch UI | ~75% | estimated: G3 done, hint peek with preview; real-screen check (G11) and Sprout design (G8) open | G8, G11 |
| PyCharm plugin | ~80% | estimated: G4 and idle events (G6) done; real-IDE use (G13) open | G13 |
| Growth (skill map, exercises, curriculum, diary) | 0% | not started, after MVP | CAPABILITY-MAP.md |

## Next

1. **MVP**: criteria 6/6 measured by agents (G1–G6 done). Left: G13 (Human), your real PyCharm run, then move the stage to alpha.
2. ~~**Evals** (G10)~~ done 2026-10-15: `eval_score` is ratcheted. Next on quality: harder cases (the checks saturate near 100), a human pass on borderline answers.
3. **Growth** module, then `#!alt`, the priority queue and the study/work toggle. (`#!review`
   became the review on Ctrl+S, 2026-10-16.)
4. A full `buddy eval --repeat 3 --triggers` with the new theory depth check, committed; G16.
