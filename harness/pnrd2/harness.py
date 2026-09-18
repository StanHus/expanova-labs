#!/usr/bin/env python3
"""PNRD#2 harness — sample · check · repair · repeat, with the Dafny verifier as the oracle.

Same shape as PNRD#1 (Lean 4 kernel on miniF2F), second sound oracle.
Benchmark: DafnyBench `hints_removed` (782 programs; specs kept, annotations stripped).

Arms
  A  one-shot: 1 sample, 1 verifier check.
  B  harness : up to N samples (temperature), each failed sample gets REPAIR repair
               turns fed the verifier's error; first program that verifies AND passes
               the guards wins. Nothing else ships.

Guards (a verified program still fails if any guard trips — these are the analog of
`#print axioms` in PNRD#1)
  * every original `requires` / `ensures` line must survive verbatim (whitespace-insensitive)
  * every original non-annotation code line must still be present (whitespace-insensitive)
  * no `assume`, `{:verify false}`, `{:axiom}`, `expect` anywhere in the output
Guard trips are counted separately as `guard_fail` so they can be audited.

Providers: any OpenAI-compatible chat endpoint (Fireworks, OpenRouter, OpenAI) or Gemini.
No third-party Python deps — urllib only. Resumable: per-problem rows are appended to
<out>.jsonl and skipped on restart.

Usage (pilot, stratified 40, Gemini):
  GEMINI_API_KEY=... python3 harness.py --provider gemini --model gemini-2.5-flash \
      --slice 40 --n 16 --repair 1 --out results/pilot-gemini25flash.json
Usage (primary arm, once a personal key exists):
  FIREWORKS_API_KEY=... python3 harness.py --provider openai \
      --base-url https://api.fireworks.ai/inference/v1 --api-key-env FIREWORKS_API_KEY \
      --model accounts/fireworks/models/gpt-oss-120b --n 16 --repair 1 --out results/full-gptoss120b.json
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, json, os, pathlib, random, re, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "DafnyBench/DafnyBench/dataset"
HINTS_REMOVED = DATA / "hints_removed"
GROUND_TRUTH = DATA / "ground_truth"

SYS = ("You are an expert in Dafny. You will be given tasks dealing with Dafny programs "
       "including precise annotations.")
TASK = ("Given a Dafny program with function signature, preconditions, postconditions, and code, "
        "but with annotations missing. Return a complete Dafny program with the strongest possible "
        "annotations (loop invariants, assert statements, decreases clauses, etc.) filled back in. "
        "Do not explain. Use exactly the same function signatures, preconditions, postconditions and "
        "code — never modify the given lines, only add annotations. Never use `assume`, "
        "`{:verify false}`, `{:axiom}` or `expect`. Reply with one ```dafny code block.\n\n")
REPAIR_MSG = ("That program did not verify. Dafny reported:\n\n{err}\n\n"
              "Fix the annotations so the program verifies. Keep every original line unchanged; "
              "only add or change annotations. Reply with one ```dafny code block.")

# $ per 1M tokens (input, output). Override with --price-in/--price-out. Stated on the page.
PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
}

# ----------------------------------------------------------------------------- guards
ANNOT_PREFIX = ("invariant", "assert", "decreases", "modifies", "reads", "ensures", "requires",
                "calc", "ghost", "lemma", "assume", "by", "//", "/*", "*", "*/", "{", "}", "reveal")
FORBIDDEN = (re.compile(r"\bassume\b"), re.compile(r"\{:verify\s+false\}"), re.compile(r"\{:axiom\}"),
             re.compile(r"\bexpect\b"))

def _squash(s: str) -> str:
    # whitespace-, parenthesis- and semicolon-insensitive: `while (i < n);` == `while i < n`
    return re.sub(r"[\s();]+", "", s)

def _spec_lines(src: str) -> list[str]:
    out, in_block = [], False
    for line in src.split("\n"):
        st = line.strip()
        if st.startswith("/*"): in_block = True
        if not in_block and not st.startswith("//") and re.match(r"^(requires|ensures)\b", st):
            out.append(_squash(st.rstrip(";")))
        if st.endswith("*/"): in_block = False
    return out

def _code_lines(src: str) -> list[str]:
    out, in_block = [], False
    for line in src.split("\n"):
        st = line.strip()
        if st.startswith("/*"): in_block = True
        if in_block:
            if st.endswith("*/"): in_block = False
            continue
        if not st or st.startswith(ANNOT_PREFIX): continue
        out.append(_squash(st))
    return out

def guards(original: str, candidate: str) -> tuple[bool, str]:
    for rx in FORBIDDEN:
        if rx.search(candidate): return False, f"forbidden:{rx.pattern}"
    cand_sq = _squash(candidate)
    for spec in _spec_lines(original):
        if spec not in cand_sq: return False, f"spec_dropped:{spec[:60]}"
    missing = [c for c in _code_lines(original) if c not in cand_sq]
    if missing: return False, f"code_changed:{missing[0][:60]}"
    return True, ""

# ----------------------------------------------------------------------------- verifier
DAFNY_SEM = threading.Semaphore(int(os.environ.get("PNRD2_DAFNY_WORKERS", "4")))

def verify(program: str, limit: int) -> tuple[bool, str, float]:
    t0 = time.time()
    with tempfile.NamedTemporaryFile("w", suffix=".dfy", delete=False) as f:
        f.write(program); path = f.name
    try:
        with DAFNY_SEM:
            r = subprocess.run(["dafny", "verify", "--verification-time-limit", str(limit), "--cores", "1", path],
                               capture_output=True, text=True, timeout=limit * 4 + 30)
        out = (r.stdout + r.stderr).replace(path, "prog.dfy")
        ok = r.returncode == 0 and "0 errors" in out and "File contains no code" not in out
    except subprocess.TimeoutExpired:
        out, ok = "verifier timeout", False
    finally:
        try: os.unlink(path)
        except OSError: pass
    return ok, out[-1500:], round(time.time() - t0, 2)

# ----------------------------------------------------------------------------- model
MODEL_SEM = threading.Semaphore(int(os.environ.get("PNRD2_MODEL_WORKERS", "8")))

class Model:
    def __init__(self, provider: str, model: str, base_url: str | None, api_key: str, max_tokens: int):
        self.provider, self.model, self.base_url, self.key, self.max_tokens = provider, model, base_url, api_key, max_tokens
    def chat(self, messages: list[dict], temperature: float) -> tuple[str, int, int]:
        for attempt in range(5):
            try:
                with MODEL_SEM:
                    return self._chat(messages, temperature)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
                code = getattr(e, "code", None)
                if code and code < 500 and code != 429: raise
                time.sleep(2 * (attempt + 1))
        raise RuntimeError("model call failed after retries")
    def _chat(self, messages, temperature):
        if self.provider == "gemini":
            return self._gemini(messages, temperature)
        url = (self.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        body = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": self.max_tokens}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        u = d.get("usage") or {}
        return d["choices"][0]["message"]["content"] or "", int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    def _gemini(self, messages, temperature):
        sys_txt = "\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.key}"
        body = {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": self.max_tokens}}
        if sys_txt: body["systemInstruction"] = {"parts": [{"text": sys_txt}]}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        u = d.get("usageMetadata") or {}
        cands = d.get("candidates") or []
        text = "".join(p.get("text", "") for p in (cands[0].get("content", {}).get("parts", []) if cands else []))
        return text, int(u.get("promptTokenCount", 0)), int(u.get("candidatesTokenCount", 0)) + int(u.get("thoughtsTokenCount", 0))

def extract_code(reply: str) -> str:
    m = re.search(r"```dafny\s*\n(.*?)```", reply, re.S) or re.search(r"```\s*\n(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip() + "\n"

# ----------------------------------------------------------------------------- one problem
def run_problem(name: str, model: Model, args, fewshot: list[dict]) -> dict:
    original = (HINTS_REMOVED / name).read_text()
    base = [{"role": "system", "content": SYS}, *fewshot, {"role": "user", "content": TASK + original}]
    row = {"id": name, "lines": original.count("\n") + 1, "arm_a": False, "arm_b": False, "b_at": 0,
           "compiles": 0, "guard_fail": 0, "tokens_in": 0, "tokens_out": 0, "verify_secs": 0.0,
           "attempts": [], "reverify_ok": None, "winner_len": 0, "error": None}

    def attempt(messages, temperature, tag):
        reply, tin, tout = model.chat(messages, temperature)
        prog = extract_code(reply)
        ok, out, secs = verify(prog, args.limit)
        row["compiles"] += 1; row["tokens_in"] += tin; row["tokens_out"] += tout; row["verify_secs"] += secs
        g_ok, g_why = guards(original, prog) if ok else (True, "")
        if ok and not g_ok: row["guard_fail"] += 1
        row["attempts"].append({"tag": tag, "verified": ok, "guard": g_ok if ok else None, "why": g_why or None,
                                "secs": secs, "tin": tin, "tout": tout})
        return (ok and g_ok), prog, out

    try:
        # Arm A — one shot, independent of arm B (no sample is shared between arms)
        ok, prog, out = attempt(base, args.temp_oneshot, "A1")
        row["arm_a"] = ok
        # Arm B — fresh samples; each failure gets `repair` turns fed the verifier error
        win = None
        for k in range(1, args.n + 1):
            ok_s, prog_s, out_s = attempt(base, args.temp, f"B{k}")
            if ok_s: win, row["b_at"] = prog_s, k; break
            for _ in range(args.repair):
                conv = base + [{"role": "assistant", "content": f"```dafny\n{prog_s}```"},
                               {"role": "user", "content": REPAIR_MSG.format(err=out_s)}]
                ok_s, prog_s, out_s = attempt(conv, args.temp, f"B{k}r")
                if ok_s: break
            if ok_s: win, row["b_at"] = prog_s, k; break
        row["arm_b"] = win is not None
        if win is not None:
            row["winner_len"] = win.count("\n")
            ok2, _, _ = verify(win, args.limit)           # flakiness check: a winner must verify twice
            row["reverify_ok"] = ok2
            if not ok2: row["arm_b"] = False; row["error"] = "reverify_failed"
            (args.outdir / "winners").mkdir(parents=True, exist_ok=True)
            (args.outdir / "winners" / name).write_text(win)
    except Exception as e:  # noqa
        row["error"] = f"{type(e).__name__}: {e}"[:300]
    return row

# ----------------------------------------------------------------------------- main
def stratified(names: list[str], k: int, seed: int) -> list[str]:
    if k >= len(names): return names
    by_len = sorted(names, key=lambda n: (HINTS_REMOVED / n).stat().st_size)
    step = len(by_len) / k
    rnd = random.Random(seed)
    return [by_len[min(len(by_len) - 1, int(i * step + rnd.random() * step))] for i in range(k)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["openai", "gemini"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url")
    ap.add_argument("--api-key-env", default=None, help="env var holding the key (default per provider)")
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--repair", type=int, default=1)
    ap.add_argument("--temp", type=float, default=0.8)
    ap.add_argument("--temp-oneshot", type=float, default=0.2)
    ap.add_argument("--limit", type=int, default=20, help="verifier time limit per check, seconds")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--slice", type=int, default=0, help="stratified subset size (0 = all)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6, help="problems in flight")
    ap.add_argument("--fewshot", default="Clover_abs.dfy", help="ground-truth file used as the one few-shot example (excluded from eval)")
    ap.add_argument("--no-fewshot", action="store_true")
    ap.add_argument("--price-in", type=float); ap.add_argument("--price-out", type=float)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    key_env = args.api_key_env or {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}[args.provider]
    key = os.environ.get(key_env)
    if not key: sys.exit(f"missing {key_env}")
    args.outdir = pathlib.Path(args.out).with_suffix(""); args.outdir.mkdir(parents=True, exist_ok=True)
    model = Model(args.provider, args.model, args.base_url, key, args.max_tokens)

    fewshot = []
    if not args.no_fewshot:
        gt = GROUND_TRUTH / args.fewshot
        hr = HINTS_REMOVED / args.fewshot.replace(".dfy", "_no_hints.dfy")
        if gt.exists() and hr.exists():
            fewshot = [{"role": "user", "content": TASK + hr.read_text()},
                       {"role": "assistant", "content": f"```dafny\n{gt.read_text()}```"}]
    names = sorted(p.name for p in HINTS_REMOVED.glob("*.dfy"))
    names = [n for n in names if n != args.fewshot.replace(".dfy", "_no_hints.dfy")]
    if args.slice: names = stratified(names, args.slice, args.seed)

    jsonl = pathlib.Path(args.out).with_suffix(".jsonl")
    done = {}
    if jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if line.strip():
                r = json.loads(line); done[r["id"]] = r
    todo = [n for n in names if n not in done]
    print(f"model={args.model} n={len(names)} todo={len(todo)} N={args.n} repair={args.repair} limit={args.limit}s", flush=True)

    lock = threading.Lock(); t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex, open(jsonl, "a") as fh:
        for i, row in enumerate(ex.map(lambda n: run_problem(n, model, args, fewshot), todo), 1):
            with lock:
                done[row["id"]] = row; fh.write(json.dumps(row) + "\n"); fh.flush()
            a = sum(r["arm_a"] for r in done.values()); b = sum(r["arm_b"] for r in done.values())
            print(f"[{len(done)}/{len(names)}] A={a} B={b} guard_fail={sum(r['guard_fail'] for r in done.values())} "
                  f"checks={sum(r['compiles'] for r in done.values())} {time.time()-t0:.0f}s  last={row['id'][:50]} "
                  f"{'ERR '+row['error'] if row['error'] else ''}", flush=True)

    rows = {n: done[n] for n in names if n in done}
    n = len(rows); pin, pout = args.price_in, args.price_out
    if pin is None or pout is None:
        pin, pout = PRICES.get(args.model, (0.0, 0.0))
    tin = sum(r["tokens_in"] for r in rows.values()); tout = sum(r["tokens_out"] for r in rows.values())
    cost = tin / 1e6 * pin + tout / 1e6 * pout
    a = sum(r["arm_a"] for r in rows.values()); b = sum(r["arm_b"] for r in rows.values())
    passk = {}
    for k in range(1, args.n + 1):
        passk[k] = sum(1 for r in rows.values() if r["arm_b"] and 0 < r["b_at"] <= k)
    summary = {
        "benchmark": "DafnyBench hints_removed", "oracle": "Dafny verifier " + subprocess.run(["dafny", "--version"], capture_output=True, text=True).stdout.strip(),
        "n": n, "BON": args.n, "REPAIR": args.repair, "fewshot": not args.no_fewshot, "temp": args.temp,
        "verifier_limit_s": args.limit, "models": {"general": args.model, "provider": args.provider},
        "rates": {"arm_a": round(a / n, 4) if n else 0, "arm_b": round(b / n, 4) if n else 0},
        "a_only": a, "b_only": b, "pass_at_k": passk,
        "kernel_checks": sum(r["compiles"] for r in rows.values()),
        "checks_on_unsolved": sum(r["compiles"] for r in rows.values() if not r["arm_b"]),
        "guard_fails": sum(r["guard_fail"] for r in rows.values()),
        "reverify_failed": sum(1 for r in rows.values() if r.get("error") == "reverify_failed"),
        "errors": sum(1 for r in rows.values() if r["error"] and r["error"] != "reverify_failed"),
        "tokens_in": tin, "tokens_out": tout, "price_per_M": [pin, pout], "cost_usd": round(cost, 4),
        "cost_per_problem_usd": round(cost / n, 5) if n else 0,
        "cost_per_b_solve_usd": round(cost / b, 4) if b else None,
        "verify_secs_total": round(sum(r["verify_secs"] for r in rows.values()), 1),
        "wall_secs": round(time.time() - t0, 1),
        "rows": {k: {kk: vv for kk, vv in v.items() if kk != "attempts"} for k, v in rows.items()},
    }
    pathlib.Path(args.out).write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "pass_at_k")}, indent=1))

if __name__ == "__main__":
    main()
