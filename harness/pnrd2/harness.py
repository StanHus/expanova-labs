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
GUARD_MSG = ("That program verified, but it broke the rules: {why}. You changed a given line or added something that is "
             "not an annotation. Restore every original line exactly; only add loop invariants, asserts, decreases "
             "clauses or helper lemmas. Reply with one ```dafny code block.")
REPAIR_MSG = ("That program did not verify. Dafny reported:\n\n{err}\n\n"
              "Fix the annotations so the program verifies. Keep every original line unchanged; "
              "only add or change annotations. Reply with one ```dafny code block.")

# $ per 1M tokens (input, output). Override with --price-in/--price-out. Stated on the page.
PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "openai.gpt-oss-120b-1:0": (0.15, 0.60),   # Amazon Bedrock list price, us-west-2
}

# ----------------------------------------------------------------------------- guards
# Rules (PREREG + addenda): annotations may be ADDED; specs and code may not change; no NEW unsound
# markers. Implementation notes after the independent re-implementation and compliance review:
#  * all checks run on comment-stripped, string-masked text (code hidden in a comment does not count)
#  * requires/ensures are compared as CLAUSES (not lines), so `requires false` on a signature line or
#    an `|| true` continuation line is caught
#  * original code lines must appear IN ORDER (ordered multiset), formatting-insensitive
#  * a forbidden marker counts only if the candidate has MORE of it than the original
FORBIDDEN = tuple(re.compile(p) for p in (
    r"\bassume\b", r"\{:\s*verify\s+false\s*\}", r"\{:\s*axiom\s*\}", r"\bexpect\b", r"@Axiom\b",
    r"@Verify\s*\(\s*false", r"\{:\s*termination\s+false\s*\}", r"\{:\s*extern\b", r"^\s*include\b",
    r"\bdecreases\s+\*"))
CLAUSE_KW = ("requires", "ensures", "modifies", "reads", "decreases", "invariant")
ANNOT_PREFIX = ("invariant", "assert", "decreases", "modifies", "reads", "ensures", "requires", "{", "}")
_CLAUSE_END = re.compile(r"\n\s*(?:requires|ensures|modifies|reads|decreases|invariant|method|function|lemma|predicate|"
                         r"class|datatype|module|const|var|while|for|if|match|assert|calc|ghost|returns)\b|\{\s*\n|\n\s*\{|;")

def _clean(src: str) -> str:
    """Drop block and line comments, mask string/char literals (line structure preserved)."""
    s = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    s = re.sub(r"//[^\n]*", "", s)
    s = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', s)
    s = re.sub(r"'(?:\\.|[^'\\\n])'", "''", s)
    return s

def _squash(s: str) -> str:
    # formatting-insensitive: whitespace, parentheses, semicolons and braces are ignored
    return re.sub(r"[\s();{}]+", "", s)

def _clauses(src: str, kw: str) -> list[str]:
    s = _clean(src); out = []
    for m in re.finditer(rf"\b{kw}\b", s):
        rest = s[m.end():]
        e = _CLAUSE_END.search(rest)
        out.append(_squash(rest[:e.start()] if e else rest))
    return out

def _code_lines(src: str) -> list[str]:
    out = []
    for line in _clean(src).split("\n"):
        st = line.strip()
        if not st or re.match(r"^(?:%s)\b" % "|".join(k for k in ANNOT_PREFIX if k.isalpha()), st) or st[0] in "{}": continue
        sq = _squash(st)
        if sq: out.append(sq)
    return out

def _strip_annotations(src: str) -> str:
    """Remove annotation constructs a model is allowed to ADD (used only as a second chance when an
    original code line was split by an inserted annotation, e.g. an assert inside a one-line block)."""
    s = re.sub(r"\bassert\b[^;{}]*?\bby\s*\{[^{}]*\}", "", src)
    s = re.sub(r"\bassert\b[^;{}]*;", "", s)
    s = re.sub(r"\b(invariant|decreases|modifies|reads)\b[^\n{]*", "", s)
    s = re.sub(r"\breveal\b[^;]*;", "", s)
    s = re.sub(r"\bghost\s+var\b[^;]*;", "", s)
    s = re.sub(r"\bcalc\s*\{[^{}]*\}", "", s)
    return s

def _ordered_contains(hay: str, needles: list[str]) -> str | None:
    pos = 0
    for n in needles:
        i = hay.find(n, pos)
        if i < 0: return n
        pos = i + len(n)
    return None

PROOF_LINE = re.compile(r"^(?:assert|assume|invariant|decreases|modifies|reads|requires|ensures|calc|forall|reveal|label|ghost|lemma|"
                        r"function|predicate|twostate|by|case|else|\{|\}|\|\||&&|==>|<==>|\+|-|\*|/|%|\.\.|:\||::|,|\)|\()")
EXEC_LINE = re.compile(r":=|\breturn\b|\bbreak\b|\byield\b|^(?:while|for|if|match|print)\b|\bnew\b")

def _added_code(original: str, candidate: str) -> str | None:
    """Return the first ADDED line that looks executable and is not a proof construct. Added lemmas,
    functions and ghost declarations (with their bodies) are allowed; so are calls to lemmas."""
    orig_lines = set(_code_lines(original))
    lemmas = set(re.findall(r"\b(?:lemma|ghost\s+method|ghost\s+function|function|predicate)\b(?:\s*\{[^}]*\})?\s+([A-Za-z_][A-Za-z_0-9']*)", _clean(candidate) + " " + _clean(original)))
    depth_skip = 0   # >0 while inside an added lemma/function/ghost block
    for line in _clean(candidate).split("\n"):
        st = line.strip()
        if not st: continue
        if depth_skip > 0:
            depth_skip += st.count("{") - st.count("}")
            if depth_skip < 0: depth_skip = 0
            continue
        if re.match(r"^(?:lemma|ghost\s+method|ghost\s+function|function|predicate|twostate)\b", st) and _squash(st) not in orig_lines:
            depth_skip = max(1, st.count("{") - st.count("}")) if "{" in st else 1
            if "{" not in st and st.endswith(("{", "{}")): pass
            continue
        sq = _squash(st)
        if not sq or sq in orig_lines: continue
        if PROOF_LINE.match(st): continue
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9']*)\s*\(", st)
        if m and m.group(1) in lemmas and ":=" not in st: continue      # lemma call as a proof hint
        if re.match(r"^[A-Za-z_][A-Za-z_0-9'.]*\s*\(.*\)\s*;?$", st): return st[:70]   # call to a non-lemma
        if EXEC_LINE.search(st): return st[:70]
    return None

def guards(original: str, candidate: str) -> tuple[bool, str]:
    co, cc = _clean(original), _clean(candidate)
    for rx in FORBIDDEN:
        if len(rx.findall(cc, re.M)) > len(rx.findall(co, re.M)): return False, f"forbidden:{rx.pattern}"
    if sorted(_clauses(original, "requires")) != sorted(_clauses(candidate, "requires")):
        return False, "requires_changed"           # added, dropped or altered precondition
    cand_ens = _clauses(candidate, "ensures")
    for cl in _clauses(original, "ensures"):
        if cl in cand_ens: cand_ens.remove(cl)
        else: return False, f"spec_dropped:ensures{cl[:50]}"
    code = _code_lines(original)
    miss = _ordered_contains(_squash(cc), code)
    if miss is not None:
        miss = _ordered_contains(_squash(_strip_annotations(cc)), code)
    if miss is not None: return False, f"code_changed:{miss[:60]}"
    added = _added_code(original, candidate)
    if added is not None: return False, f"code_added:{added}"
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
        m = re.search(r"(\d+) verified, 0 errors", out)
        ok = r.returncode == 0 and bool(m) and int(m.group(1)) > 0   # an empty program is not a proof
    except subprocess.TimeoutExpired:
        out, ok = "verifier timeout", False
    finally:
        try: os.unlink(path)
        except OSError: pass
    return ok, out[-1500:], round(time.time() - t0, 2)

# ----------------------------------------------------------------------------- model
MODEL_SEM = threading.Semaphore(int(os.environ.get("PNRD2_MODEL_WORKERS", "3")))

class RateLimiter:
    """Global requests-per-minute pacing so a free-tier key is never burst-exhausted."""
    def __init__(self, rpm: float):
        self.min_gap = 60.0 / rpm if rpm > 0 else 0.0
        self.lock, self.next_ok = threading.Lock(), 0.0
    def wait(self):
        if not self.min_gap: return
        with self.lock:
            now = time.time(); t = max(now, self.next_ok); self.next_ok = t + self.min_gap
        if t > now: time.sleep(t - now)

class Model:
    def __init__(self, provider: str, model: str, base_url: str | None, api_key: str, max_tokens: int, rpm: float = 0):
        self.provider, self.model, self.base_url, self.key, self.max_tokens = provider, model, base_url, api_key, max_tokens
        self.limiter = RateLimiter(rpm)
    def chat(self, messages: list[dict], temperature: float) -> tuple[str, int, int]:
        last = None
        for attempt in range(8):
            try:
                with MODEL_SEM:
                    self.limiter.wait()
                    return self._chat(messages, temperature)
            except urllib.error.HTTPError as e:
                body = ""
                try: body = e.read().decode()[:300]
                except Exception: pass
                last = f"HTTP {e.code} {body}"
                if e.code < 500 and e.code not in (408, 429): raise RuntimeError(last)
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = float(ra) if ra and ra.replace(".", "", 1).isdigit() else min(90, 5 * 2 ** attempt)
                time.sleep(wait + random.random() * 2)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError) as e:
                last = f"{type(e).__name__}: {e}"[:200]
                time.sleep(min(60, 5 * 2 ** attempt))
        raise RuntimeError(f"model call failed after retries: {last}")
    def _chat(self, messages, temperature):
        if self.provider == "gemini":
            return self._gemini(messages, temperature)
        if self.provider == "bedrock":
            return self._bedrock(messages, temperature)
        url = (self.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        body = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": self.max_tokens}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        u = d.get("usage") or {}
        return d["choices"][0]["message"]["content"] or "", int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    _bedrock_client = None
    def _bedrock(self, messages, temperature):
        import boto3  # only needed for this provider
        if Model._bedrock_client is None:
            session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE"), region_name=os.environ.get("AWS_REGION", "us-west-2"))
            Model._bedrock_client = session.client("bedrock-runtime")
        sys_txt = [{"text": m["content"]} for m in messages if m["role"] == "system"]
        msgs = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
        kw = {"modelId": self.model, "messages": msgs, "inferenceConfig": {"maxTokens": self.max_tokens, "temperature": temperature}}
        if sys_txt: kw["system"] = sys_txt
        try:
            d = Model._bedrock_client.converse(**kw)
        except Exception as e:  # botocore throttling -> retryable
            name = type(e).__name__
            if "Throttling" in name or "TooManyRequests" in str(e) or "ServiceUnavailable" in name:
                raise urllib.error.HTTPError("bedrock", 429, str(e)[:200], {}, None)
            raise
        text = "".join(c.get("text", "") for c in d["output"]["message"]["content"] if "text" in c)
        u = d.get("usage") or {}
        return text, int(u.get("inputTokens", 0)), int(u.get("outputTokens", 0))

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
        if not ok:
            fd = args.outdir / "failed"; fd.mkdir(parents=True, exist_ok=True)   # sample of failures for audit
            if row["compiles"] < 3: (fd / f"{name}.{tag}.dfy").write_text(f"// verifier: {out[-400:]}\n" + prog)
        row["compiles"] += 1; row["tokens_in"] += tin; row["tokens_out"] += tout; row["verify_secs"] += secs
        g_ok, g_why = guards(original, prog) if ok else (True, "")
        if ok and not g_ok:
            row["guard_fail"] += 1
            # keep every verified-but-blocked candidate so the guard itself can be audited later
            gd = args.outdir / "guard_trips"; gd.mkdir(parents=True, exist_ok=True)
            (gd / f"{name}.{tag}.dfy").write_text(f"// guard: {g_why}\n" + prog)
            out = "GUARD:" + g_why          # the repair turn must be told the real reason, not "did not verify"
        row["attempts"].append({"tag": tag, "verified": ok, "guard": g_ok if ok else None, "why": g_why or None,
                                "secs": secs, "tin": tin, "tout": tout})
        return (ok and g_ok), prog, out

    try:
        # Arm A — one shot, independent of arm B (no sample is shared between arms)
        ok, prog, out = attempt(base, args.temp_oneshot, "A1")
        row["arm_a"] = ok
        if ok:
            (args.outdir / "winners_a").mkdir(parents=True, exist_ok=True)
            (args.outdir / "winners_a" / name).write_text(prog)
            ok_a2, _, _ = verify(prog, args.limit)
            row["reverify_a_ok"] = ok_a2
            if not ok_a2: row["arm_a"] = False; row["error"] = (row["error"] or "") + "reverify_a_failed;"
        # Arm B — fresh samples; each failure gets `repair` turns fed the verifier error
        win = None
        for k in range(1, args.n + 1):
            ok_s, prog_s, out_s = attempt(base, args.temp, f"B{k}")
            if ok_s: win, row["b_at"] = prog_s, k; break
            for _ in range(args.repair):
                fb = GUARD_MSG.format(why=out_s[6:]) if out_s.startswith("GUARD:") else REPAIR_MSG.format(err=out_s)
                conv = base + [{"role": "assistant", "content": f"```dafny\n{prog_s}```"},
                               {"role": "user", "content": fb}]
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
    ap.add_argument("--provider", choices=["openai", "gemini", "bedrock"], required=True)
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
    ap.add_argument("--rpm", type=float, default=0, help="global model requests per minute (0 = unpaced)")
    ap.add_argument("--price-in", type=float); ap.add_argument("--price-out", type=float)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    key_env = args.api_key_env or {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "bedrock": "AWS_PROFILE"}[args.provider]
    key = os.environ.get(key_env)
    if not key: sys.exit(f"missing {key_env}")
    args.outdir = pathlib.Path(args.out).with_suffix(""); args.outdir.mkdir(parents=True, exist_ok=True)
    model = Model(args.provider, args.model, args.base_url, key, args.max_tokens, args.rpm)

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
                r = json.loads(line)
                # rows that died on infrastructure (rate limits, network) are retried; verdict rows are kept
                if r.get("error") and r["error"] != "reverify_failed": continue
                done[r["id"]] = r
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
