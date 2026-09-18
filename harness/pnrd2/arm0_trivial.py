#!/usr/bin/env python3
"""Arm 0: verify every hints_removed program AS-IS (no model). Programs that
verify with zero hints are 'trivial' and are reported separately."""
import json, subprocess, sys, time, concurrent.futures as cf, pathlib
ROOT = pathlib.Path(__file__).parent / "DafnyBench/DafnyBench/dataset/hints_removed"
files = sorted(ROOT.glob("*.dfy"))
LIMIT = 20
def verify(p):
    t0 = time.time()
    try:
        r = subprocess.run(["dafny","verify","--verification-time-limit",str(LIMIT),"--cores","1",str(p)],
                           capture_output=True, text=True, timeout=LIMIT*3+30)
        out = r.stdout + r.stderr
        ok = r.returncode == 0 and "0 errors" in out
    except subprocess.TimeoutExpired:
        out, ok = "TIMEOUT", False
    return p.name, ok, round(time.time()-t0,1), out[-300:]
res = {}
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for i,(name, ok, dt, tail) in enumerate(ex.map(verify, files), 1):
        res[name] = {"verifies_as_is": ok, "secs": dt}
        if i % 100 == 0: print(f"{i}/{len(files)} done, trivial so far {sum(v['verifies_as_is'] for v in res.values())}", flush=True)
triv = sum(v["verifies_as_is"] for v in res.values())
json.dump({"n": len(res), "trivial": triv, "limit_s": LIMIT, "rows": res}, open("arm0_trivial.json","w"), indent=1)
print(f"DONE n={len(res)} trivial(verify with no hints)={triv} ({triv/len(res):.1%}) mean_secs={sum(v['secs'] for v in res.values())/len(res):.1f}")
