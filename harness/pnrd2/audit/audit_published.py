#!/usr/bin/env python3
"""PNRD#2 audit lane -- re-verify the LLM outputs DafnyBench published, with today's Dafny,
and apply the PNRD#2 harness guard to each one.

For every model in results/reconstructed_files/<model>_outputs.json and every output:
  1. extract the program (outputs are already extracted code; stray markdown fences are stripped)
  2. `dafny verify --verification-time-limit 20 --cores 1` (harness.verify, identical oracle)
  3. harness.guards(original, candidate) with original = the matching hints_removed file
  4. record verified, guard_ok, guard_reason (+ claimed success from results_summary csv)

Inputs. Default source is <this dir>/src/, an extraction of the DafnyBench GitHub tarball at commit
0cd28feed9cd0179b07fdb9d002f8c39063658e4 (HEAD of main, 2024-12-12 -- the same commit the
pnrd2/DafnyBench shallow clone made today points at). Reason: pnrd2/ lives in an iCloud-synced
folder on a 98%-full volume and iCloud evicted the whole clone -- and everything written to
pnrd2/audit/ -- within minutes (APFS `dataless`, reads block forever). Set AUDIT_SRC=<dir> to point
at another checkout. EVERYTHING is read into memory at startup so a later eviction cannot stall
the run. Because of the eviction the run itself executes from a non-iCloud scratch mirror
(/tmp/pnrd2-audit/audit) and the finished artifacts are copied into pnrd2/audit/.

Guard implementation. `import harness` (<AUDIT_PNRD2>/harness.py, default ../harness.py) is used
when that file is readable; when it is dataless/missing the verbatim snapshot
harness_guard_snapshot.py is used instead. The summary records which, and (when both are
available) whether their guard source text is identical.

Resumable: per-row results are appended to published_audit.jsonl and skipped on restart.
Final output: published_audit.json (per-model totals + per-file rows).
Read-only w.r.t. harness.py / PREREG.md / DafnyBench.
"""
from __future__ import annotations
import concurrent.futures as cf, csv, importlib, inspect, json, os, pathlib, re, subprocess, sys, threading, time

HERE = pathlib.Path(__file__).resolve().parent            # .../audit (or its scratch mirror)
PNRD2 = pathlib.Path(os.environ.get("AUDIT_PNRD2", str(HERE.parent)))   # where harness.py lives
MODELS = ["claude-3-opus", "codellama-7b", "gpt-3.5-turbo", "gpt-4-turbo", "gpt-4o"]
LIMIT = int(os.environ.get("AUDIT_LIMIT", "20"))
WORKERS = int(os.environ.get("AUDIT_WORKERS", "4"))
JSONL = HERE / "published_audit.jsonl"
OUT = HERE / "published_audit.json"
SRC_COMMIT = "0cd28feed9cd0179b07fdb9d002f8c39063658e4"


def is_dataless(p: pathlib.Path) -> bool:
    """APFS/iCloud-evicted file: size > 0 but zero allocated blocks. Reading it may block forever."""
    try:
        st = p.stat()
        return st.st_size > 0 and getattr(st, "st_blocks", 1) == 0
    except OSError:
        return True


def pick_source() -> pathlib.Path:
    env = os.environ.get("AUDIT_SRC")
    if env:
        return pathlib.Path(env)
    if (HERE / "src/DafnyBench/dataset/hints_removed").exists():
        return HERE / "src"
    return PNRD2 / "DafnyBench"


def load_guard_impl():
    """Real harness when readable, verbatim snapshot otherwise. Returns (module, info dict)."""
    hp = PNRD2 / "harness.py"
    info = {"harness_py": str(hp), "harness_py_exists": hp.exists(), "harness_py_dataless": is_dataless(hp),
            "used": None, "snapshot_matches_harness": None}
    sys.path.insert(0, str(HERE))
    snap = importlib.import_module("harness_guard_snapshot")
    if hp.exists() and not info["harness_py_dataless"]:
        try:
            sys.path.insert(0, str(PNRD2))
            real = importlib.import_module("harness")
            info["used"] = "harness.py"
            same = True
            for name in ("_req_lines", "_squash", "_spec_lines", "_code_lines", "guards", "verify"):
                same = same and inspect.getsource(getattr(real, name)) == inspect.getsource(getattr(snap, name))
            same = same and real.ANNOT_PREFIX == snap.ANNOT_PREFIX and [r.pattern for r in real.FORBIDDEN] == [r.pattern for r in snap.FORBIDDEN]
            info["snapshot_matches_harness"] = same
            return real, info
        except Exception as e:  # noqa
            info["harness_import_error"] = f"{type(e).__name__}: {e}"[:200]
    info["used"] = "harness_guard_snapshot.py (verbatim copy; harness.py unreadable/dataless)"
    return snap, info


FENCE_RX = re.compile(r"```(?:dafny|Dafny|DAFNY)?[^\n]*\n(.*?)```", re.S)


def extract_program(text):
    """Outputs are already extracted code. If a stray fence survived, take the fenced body."""
    if text is None:
        return "", False
    m = FENCE_RX.search(text)
    if m:
        return m.group(1).strip() + "\n", True
    if "```" in text:
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        return "\n".join(lines).strip() + "\n", True
    return text.strip() + "\n", False


def load_claims(csv_dir: pathlib.Path, model: str):
    """test_file -> raw success_on_attempt_# value. Returns (map, parse_error)."""
    p = csv_dir / f"{model}_results.csv"
    try:
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh)
            col = next((c for c in rd.fieldnames or [] if c.startswith("success")), None)
            if col is None:
                return {}, f"no success column in {p.name}: {rd.fieldnames}"
            m = {}
            for r in rd:
                tf = (r.get("test_file") or "").strip()
                if tf:
                    m[tf] = (r.get(col) or "").strip()
            return m, None
    except Exception as e:  # noqa
        return {}, f"{type(e).__name__}: {e}"


def claimed_ok(raw):
    if raw is None or raw == "":
        return None
    if raw.lower() == "failed":
        return False
    try:
        int(raw)
        return True            # an attempt index (0-based) means it verified on that attempt
    except ValueError:
        return None


def reason_bucket(r):
    if r is None:
        return None
    return r.split(":", 1)[0]


class Audit:
    def __init__(self, H, originals):
        self.H, self.originals = H, originals

    def one(self, job):
        model, tid, tf, text = job["model"], job["test_ID"], job["test_file"], job["llm_output"]
        row = {"model": model, "test_ID": tid, "test_file": tf, "claimed_raw": job["claimed_raw"],
               "claimed_success": claimed_ok(job["claimed_raw"]), "had_fence": False,
               "original_found": tf in self.originals, "verified": False, "guard_ok": None, "guard_reason": None,
               "verify_secs": 0.0, "dafny_tail": None, "prog_len": 0}
        prog, fenced = extract_program(text)
        row["had_fence"], row["prog_len"] = fenced, len(prog)
        if not prog.strip():
            row["dafny_tail"], row["guard_ok"], row["guard_reason"] = "empty output", False, "empty_output"
            return row
        ok, out, secs = self.H.verify(prog, LIMIT)
        row["verified"], row["verify_secs"], row["dafny_tail"] = ok, secs, out[-400:]
        if tf in self.originals:
            g_ok, g_why = self.H.guards(self.originals[tf], prog)
            row["guard_ok"], row["guard_reason"] = g_ok, (g_why or None)
        else:
            row["guard_ok"], row["guard_reason"] = None, "original_missing"
        return row


def main():
    src = pick_source()
    hints_dir, out_dir, csv_dir = src / "DafnyBench/dataset/hints_removed", src / "results/reconstructed_files", src / "results/results_summary"
    H, guard_info = load_guard_impl()
    H.DAFNY_SEM = threading.Semaphore(WORKERS)   # verify() reads this global at call time

    # ---- read every input into memory now (iCloud may evict files later)
    t_load = time.time()
    dl = [p.name for p in hints_dir.glob("*.dfy") if is_dataless(p)]
    if dl:
        sys.exit(f"{len(dl)} hints_removed files under {hints_dir} are iCloud-dataless (would block); "
                 f"point AUDIT_SRC at a hydrated copy. e.g. {dl[:3]}")
    originals = {p.name: p.read_text() for p in sorted(hints_dir.glob("*.dfy"))}
    jobs, claims_meta = [], {}
    for model in MODELS:
        d = json.load(open(out_dir / f"{model}_outputs.json"))
        claims, err = load_claims(csv_dir, model)
        claims_meta[model] = {"csv_rows": len(claims), "csv_error": err,
                              "csv_claimed_success": sum(1 for v in claims.values() if claimed_ok(v)),
                              "csv_claimed_failed": sum(1 for v in claims.values() if claimed_ok(v) is False)}
        for key, e in d.items():
            tf = e.get("test_file") or ""
            jobs.append({"model": model, "test_ID": e.get("test_ID", key), "test_file": tf,
                         "llm_output": e.get("llm_output"), "claimed_raw": claims.get(tf)})
    print(f"source={src} originals={len(originals)} jobs={len(jobs)} loaded in {time.time()-t_load:.1f}s; guard impl: {guard_info}", flush=True)

    done = {}
    if JSONL.exists():
        for line in JSONL.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r["model"], r["test_ID"])] = r
    todo = [j for j in jobs if (j["model"], j["test_ID"]) not in done]
    dafny_v = subprocess.run(["dafny", "--version"], capture_output=True, text=True).stdout.strip()
    print(f"dafny={dafny_v} limit={LIMIT}s workers={WORKERS} jobs={len(jobs)} done={len(done)} todo={len(todo)}", flush=True)
    audit = Audit(H, originals)
    t0 = time.time()
    lock = threading.Lock()
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex, open(JSONL, "a") as fh:
        for i, row in enumerate(ex.map(audit.one, todo), 1):
            with lock:
                done[(row["model"], row["test_ID"])] = row
                fh.write(json.dumps(row) + "\n")
                fh.flush()
            if i % 25 == 0 or i == len(todo):
                v = sum(1 for r in done.values() if r["verified"])
                g = sum(1 for r in done.values() if r["verified"] and r["guard_ok"])
                el = time.time() - t0
                rate = i / el if el else 0
                eta = (len(todo) - i) / rate if rate else 0
                print(f"[{len(done)}/{len(jobs)}] verified={v} verified+guard={g} {el:.0f}s eta={eta/60:.1f}m "
                      f"last={row['model']}:{row['test_file'][:45]}", flush=True)

    # ---- cross-check: recompute the guard for every row from the in-memory source and compare
    # with what was recorded. The guard is deterministic and cheap, so the recomputed value is
    # authoritative (rows whose original was read while iCloud was evicting it may have seen a
    # truncated/empty file).
    by_job = {(j["model"], j["test_ID"]): j for j in jobs}
    guard_mismatch = []
    for k, r in done.items():
        j = by_job.get(k)
        if not j or r["guard_reason"] == "empty_output" or j["test_file"] not in originals:
            continue
        prog, _ = extract_program(j["llm_output"])
        g_ok, g_why = H.guards(originals[j["test_file"]], prog)
        if g_ok != r["guard_ok"] or (g_why or None) != r["guard_reason"]:
            guard_mismatch.append({"model": k[0], "test_ID": k[1], "test_file": j["test_file"], "verified": r["verified"],
                                   "recorded": r["guard_reason"], "recomputed": g_why or None})
            r["guard_ok"], r["guard_reason"], r["guard_recomputed"] = g_ok, (g_why or None), True
            r["original_found"] = True

    # ---- originals that can never pass the guard (they themselves contain a forbidden marker)
    forbidden_in_original = {}
    for name, s in originals.items():
        for rx in H.FORBIDDEN:
            if rx.search(s):
                forbidden_in_original[name] = rx.pattern
                break

    per_model, rows_out = {}, {}
    for model in MODELS:
        rows = sorted((r for r in done.values() if r["model"] == model), key=lambda r: r["test_ID"])
        rows_out[model] = rows
        trips = [r for r in rows if r["verified"] and r["guard_ok"] is False]
        by_reason, all_trip_reasons = {}, {}
        for r in trips:
            b = reason_bucket(r["guard_reason"]) or "unknown"
            by_reason[b] = by_reason.get(b, 0) + 1
        for r in rows:
            if r["guard_ok"] is False:
                b = reason_bucket(r["guard_reason"]) or "unknown"
                all_trip_reasons[b] = all_trip_reasons.get(b, 0) + 1
        claimed = sum(1 for r in rows if r["claimed_success"] is True)
        ver = sum(1 for r in rows if r["verified"])
        vg = sum(1 for r in rows if r["verified"] and r["guard_ok"] is True)
        per_model[model] = {
            "n_outputs": len(rows),
            "claimed_success_in_outputs": claimed,
            "claimed_success_unparseable": sum(1 for r in rows if r["claimed_success"] is None),
            "csv": claims_meta[model],
            "verifies_today": ver,
            "verifies_and_guard_ok": vg,
            "guard_trips_on_verified": len(trips),
            "guard_trip_reasons_on_verified": by_reason,
            "guard_trips_on_verified_where_original_itself_forbidden": sum(1 for r in trips if r["test_file"] in forbidden_in_original),
            "guard_fail_on_all_outputs": sum(1 for r in rows if r["guard_ok"] is False),
            "guard_fail_reasons_on_all_outputs": all_trip_reasons,
            "claimed_success_but_fails_today": sum(1 for r in rows if r["claimed_success"] is True and not r["verified"]),
            "claimed_failed_but_verifies_today": sum(1 for r in rows if r["claimed_success"] is False and r["verified"]),
            "claimed_success_and_verifies_today": sum(1 for r in rows if r["claimed_success"] is True and r["verified"]),
            "claimed_success_verifies_and_guard_ok": sum(1 for r in rows if r["claimed_success"] is True and r["verified"] and r["guard_ok"] is True),
            "had_fence": sum(1 for r in rows if r["had_fence"]),
            "original_missing": sum(1 for r in rows if not r["original_found"]),
            "empty_output": sum(1 for r in rows if r["guard_reason"] == "empty_output"),
            "verifier_timeouts": sum(1 for r in rows if r["dafny_tail"] == "verifier timeout"),
            "verify_secs_total": round(sum(r["verify_secs"] for r in rows), 1),
            "example_trips": [{"test_file": r["test_file"], "test_ID": r["test_ID"], "reason": r["guard_reason"],
                               "claimed_raw": r["claimed_raw"]} for r in trips[:3]],
        }
    summary = {
        "audit": "PNRD#2 published-output audit of DafnyBench reconstructed LLM outputs",
        "dafny": dafny_v, "verifier_limit_s": LIMIT, "cores": 1, "workers": WORKERS,
        "source": {"dir": str(src), "dafnybench_commit": SRC_COMMIT if src == HERE / "src" else "local clone (pnrd2/DafnyBench)"},
        "guard": "harness.guards(original=hints_removed/<test_file>, candidate=llm_output)",
        "guard_impl": guard_info,
        "guard_recheck_mismatches": guard_mismatch,
        "originals_with_forbidden_marker": {"count": len(forbidden_in_original), "files": forbidden_in_original},
        "claimed_success_semantics": "results_summary csv column success_on_attempt_#: integer = verified on that (0-based) attempt in the 2024 paper run; 'failed' = never verified",
        "caveats": [
            "Dafny version drift: the 2024 DafnyBench paper used a Dafny 4.x of that time; this audit uses dafny 4.11.0. Programs may verify/fail differently (resolver changes, Boogie/Z3 changes, new warnings/errors).",
            "Time limit: this audit uses --verification-time-limit 20 --cores 1 per file (the limit is per assertion batch, so large files can run longer); the paper's per-file timeout and core count may differ, so borderline programs can flip either way.",
            "Guard is stricter than DafnyBench's own success criterion (DafnyBench only required the model to preserve preconditions/postconditions; the PNRD#2 guard also requires every original code line to survive, an identical multiset of requires clauses, and forbids assume / axioms / extern / include / decreases *).",
            "Whitespace-insensitive line matching can be tripped by benign reformatting (e.g. splitting a one-line if/else across lines), so guard trips are an upper bound on spec/code rewrites; see per-file rows.",
            "Some hints_removed originals themselves contain a forbidden marker (see originals_with_forbidden_marker); any output that keeps such a line trips the guard, and any output that drops it trips code_changed -- those programs are guard-unpassable by construction.",
            "Outputs with had_fence=true had a stray markdown fence stripped before verification.",
            "Inputs are the GitHub tarball of DafnyBench at commit 0cd28fee... (same commit as the local shallow clone) because iCloud evicted the local clone; the run executed from a non-iCloud scratch mirror and the artifacts were copied into pnrd2/audit/.",
        ],
        "totals": {"n_outputs": sum(m["n_outputs"] for m in per_model.values()),
                   "verifies_today": sum(m["verifies_today"] for m in per_model.values()),
                   "verifies_and_guard_ok": sum(m["verifies_and_guard_ok"] for m in per_model.values()),
                   "guard_trips_on_verified": sum(m["guard_trips_on_verified"] for m in per_model.values()),
                   "wall_secs_this_run": round(time.time() - t0, 1)},
        "per_model": per_model,
        "rows": rows_out,
    }
    OUT.write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "originals_with_forbidden_marker")}, indent=1), flush=True)
    print("originals_with_forbidden_marker:", len(forbidden_in_original), flush=True)


if __name__ == "__main__":
    main()
