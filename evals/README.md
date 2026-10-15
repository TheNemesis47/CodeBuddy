# evals

How good the buddy's answers are, as one number that only goes up (G10).

- `cases/*.json`: 29 Python snippets, beginner to intermediate (18 `hint`, 8 `#?`, 3
  `#!teoria`), each with a cursor line, expected concept regexes, forbidden "fix" regexes, the
  corrected line(s) and a rubric. Format: `schema/case.schema.json`.
- `results/<date>[-N].json`: one file per run, per-case checks, answers, judge grades and the
  total. The latest **committed** complete result is the `eval_score` in `quality/floors.json`.

```sh
cd brain
uv run buddy eval --repeat 3                          # hints only, on the local engine (:8080 / :8000)
uv run buddy eval --repeat 3 --triggers --judge local # + #? / #!teoria on Claude (uses quota) + rubric judge
uv run buddy eval --only hint-missing-with            # one case
uv run buddy eval --rescore ../evals/results/X.json   # re-check saved answers after editing a case
```

Score: each answer gets 5 deterministic checks (concept, shape, no_leak, no_fix, language; theory
has no shape rule); a case scores the fraction it passes, averaged over its runs; the total is the
mean over cases × 100. The LLM judge (1–5) is reported apart, not ratcheted: the local judge is
noisy and sometimes rewards answers that give the fix away. Hints are sampled at temperature 0.6,
so use `--repeat 3` for hints: single runs move by ±2 points.

Adding a case: write `cases/<id>.json` (id = file name), run `uv run pytest tests/test_evals.py`
(schema, trigger line, regexes compile, the fix isn't already in the code), then a full run.
Committing a new result with a lower total fails `scripts/check`: fix the prompt, not the floor.
