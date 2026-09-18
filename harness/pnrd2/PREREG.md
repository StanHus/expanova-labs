# PNRD#2 — pre-registration

Written and committed **before** any harness result existed. The commit hash of this file is the
timestamp. Nothing below is edited after results arrive; corrections go in a dated addendum.

## Question

PNRD#1 showed that a cheap open model plus a sound oracle (the Lean 4 kernel) nearly doubled its
verified solve rate on miniF2F (24.6% → 47.1%). The approach page claims the same mechanism
generalizes to spec-bound code. That claim has no number behind it. PNRD#2 tests it on a second sound
oracle that is available at selection time: the **Dafny verifier**.

## Design

- Benchmark: DafnyBench `hints_removed`, 782 programs (specs kept, annotations stripped). One
  program (`Clover_abs`) is reserved as the single few-shot example and excluded from evaluation.
- Oracle: `dafny verify` (4.11.0), 20 s verification time limit per check, `--cores 1`.
- Harness shape identical to PNRD#1: best-of-N sampling (N = 16, temperature 0.8) with one repair turn
  per failed sample fed the verifier's error; first program that verifies **and passes the guards**
  wins. One-shot baseline: one sample at temperature 0.2.
- Guards (the analog of `#print axioms`): every original `requires`/`ensures` line and every original
  code line must survive verbatim (whitespace-insensitive); no `assume`, `{:verify false}`,
  `{:axiom}`, `expect`. A verified program that trips a guard is a **fail**, counted separately.
- Every winner is re-verified once. A winner that does not verify twice is a fail.
- Arm 0 (no model): every stripped program is verified as-is first. Programs that verify with no
  hints are reported as *trivial* and results are also given on the non-trivial subset.

## Models

- **Primary arm: `gpt-oss-120b`** — the same open model as PNRD#1, so only the oracle changes.
  Blocked at pre-registration time: no personal API key on the lab machine reaches it. Runs when a
  personal Fireworks or OpenRouter key exists.
- **Pilot arm: `gemini-2.5-flash`** — the only model a personal key reaches today. Cheap, closed
  weights. Reported as its own row, never blended with the primary arm.
- Registered follow-up, not run: `Ternary-Bonsai-2-27B` locally (≈1.7 bits/weight). Blocked by disk
  on the lab machine, not by design.

## Predictions (written before running)

1. Harness lift over one-shot on the non-trivial subset: **≥ +10 points** for whichever model runs.
2. Saturation: **≥ 80%** of harness solves land by attempt 8 (PNRD#1: 109/115 = 95%).
3. Compute waste: **≥ 70%** of verifier checks are spent on programs that never solve
   (PNRD#1: 86%). This is the number PNRD#3 should attack.
4. Guard trips will be **non-zero**. A verifier-passing, spec-weakening answer will appear at least
   once in 782 programs; that is why the guard exists.

## Gate (decided now)

- **SHIP** if prediction 1 holds and guard trips are reported, with zero unguarded false positives
  (a shipped "solve" later found to weaken the spec kills the page).
- **PARTIAL** if lift is +5 to +10: publish as "law holds weakly on this oracle", no headline claim.
- **KILL** if lift < +5, or any reverified winner fails, or the guard is found bypassable. The KILL
  is published with the same prominence a SHIP would get.

## What is not claimed

Not that Dafny annotation is hard for frontier models (it isn't; DafnyBench's own protocol already
includes error feedback). The claim under test is narrower: the *same harness shape* produces a
*verified* lift on a *second* sound oracle, with the cost of that lift accounted for per verifier check.

---

## Addendum 1 — 2026-09-18 12:20 CEST (after pre-registration, before any result)

- A 3-program smoke test of the harness ran on `gemini-2.5-flash` to prove the pipeline end to end
  (verifier, guards, re-verification, cost accounting). It is not a result and is not published.
- The pilot arm could not run: the only personal Gemini key on the lab machine is free tier with a
  quota of **20 requests per day** for `gemini-2.5-flash` (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`),
  exhausted before the first program completed. Other Gemini tiers are unavailable to the key.
- Arm 0 completed: **166 of 782** stripped programs (21.2%) verify with zero hints under the 20 s limit.
- The harness gained a global requests-per-minute limiter (`--rpm`) and now retries rows that failed on
  infrastructure instead of counting them. Neither changes the design or the gate.
- Nothing above the addendum line was edited.

## Addendum 2 — 2026-09-18 12:40 CEST (before the primary run)

- **Route found for the primary arm:** `gpt-oss-120b` via Amazon Bedrock (`openai.gpt-oss-120b-1:0`,
  us-west-2) on a personal AWS account. Same open weights as PNRD#1; provider differs (Bedrock vs
  Fireworks). Bedrock list price used for cost accounting.
- **Guard tightened before running:** the registered guard required original `requires`/`ensures`
  lines to survive but did not forbid *adding* a `requires` clause — `requires false` would verify
  anything. The multiset of `requires` clauses must now equal the original's exactly. Also banned:
  `@Axiom`, `@Verify(false)`, `{:termination false}`, `{:extern}`, `include`, `decreases *`.
  This makes the guard stricter, never looser; predictions and gate unchanged.
- A second, independent implementation of the guard (written from this document, not from the
  harness code) will re-check every winner; disagreements are published.
- Nothing above Addendum 1 was edited.

## Addendum 3 — 2026-09-18 13:45 CEST (after 57 programs of run 1; run 1 discarded, run 2 started from scratch)

- Run 1 showed 39 guard trips in 57 programs. Inspection of the reasons: 21 were the code-line check
  tripping on **formatting** (`{` moved to its own line after a signature; an inline `// comment`
  dropped from a spec line), not on changed code. 3 were genuine `assume` cheats. Some `spec_dropped`
  trips were the model rewriting a spec's *text* (e.g. dropping a `: int` binder) — still counted as
  trips: the rule is verbatim modulo formatting, and it stays that way.
- Fix: normalization now ignores whitespace, parentheses, semicolons, **braces**, and **trailing
  `//` comments**. Identifiers, operators, types and literals must still match exactly. This makes the
  guard looser only on formatting; it does not change what counts as a spec or code change.
- Run 1's partial rows (57) are kept in `results/aborted/run1-strictguard.jsonl` for the record and
  excluded from all reported numbers. Run 2 restarts from zero with the fixed guard and higher
  concurrency (12 programs in flight, 16 model calls, 6 verifier processes).
- Every verified-but-blocked candidate is now saved under `results/<run>/guard_trips/` so the guard
  itself can be audited after the fact; a sample of verifier failures is saved under `failed/`.
- Predictions and gate unchanged. Nothing above Addendum 1 was edited.
