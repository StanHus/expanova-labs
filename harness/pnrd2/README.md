# PNRD#2 harness

Sample · check · repair · repeat, with the **Dafny verifier** as the oracle. Same shape as PNRD#1
(Lean 4 kernel on miniF2F), second sound oracle. Read `PREREG.md` first — the gate was fixed before
any result existed.

## Reproduce

```bash
brew install dafny                      # 4.11.0 was used
git clone --depth 1 https://github.com/sun-wendy/DafnyBench.git   # inside this directory
python3 arm0_trivial.py                 # model-free baseline: which stripped programs verify as-is

# pilot arm (closed weights, the only model a personal key reached on the lab machine)
GEMINI_API_KEY=... python3 harness.py --provider gemini --model gemini-2.5-flash \
    --slice 40 --n 16 --repair 1 --seed 1 --out results/pilot-gemini25flash.json

# primary arm — same open model as PNRD#1; needs a personal Fireworks/OpenRouter key
FIREWORKS_API_KEY=... python3 harness.py --provider openai \
    --base-url https://api.fireworks.ai/inference/v1 --api-key-env FIREWORKS_API_KEY \
    --model accounts/fireworks/models/gpt-oss-120b --n 16 --repair 1 --out results/full-gptoss120b.json
```

No Python dependencies beyond the standard library. Runs are resumable (`<out>.jsonl`). Every
winning program is written to `results/<run>/winners/` so any solve can be re-verified by hand:

```bash
dafny verify --verification-time-limit 20 results/pilot-gemini25flash/winners/<file>.dfy
```

## What counts as a solve

A program is a solve only if **all** of these hold:

1. `dafny verify` exits 0 with `0 errors` within the time limit;
2. every original `requires` / `ensures` line survives verbatim (whitespace-insensitive);
3. every original code line survives verbatim (whitespace-insensitive) — annotations may be added, code may not be rewritten;
4. no `assume`, `{:verify false}`, `{:axiom}`, `expect` anywhere;
5. it verifies a **second** time.

Guard trips (1 passes, 2–4 fail) are counted in `guard_fail` and are not solves.

## Output

`<out>.json` carries the summary (rates, pass@k, verifier checks, checks spent on never-solved
programs, guard trips, tokens, cost at the stated per-million prices) plus one row per program.
The site page reads this file directly; no number on the page is typed by hand.
