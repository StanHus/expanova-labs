#!/usr/bin/env python3
"""
reverify.py — independent re-implementation of PNRD#2's "what counts as a solve".

Written from PREREG.md (incl. Addendum 2) and README.md ONLY, without reading harness.py.

A winner file W (candidate) for an original O (DafnyBench hints_removed) is a SOLVE iff ALL hold:

  (a) verify1  : `dafny verify --verification-time-limit T --cores 1 W` exits 0 and prints "0 errors"
  (b) spec     : every original `requires` / `ensures` LINE survives verbatim (whitespace-insensitive)
  (c) code     : every original non-annotation LINE survives verbatim (whitespace-insensitive),
                 in the original order (additions are allowed; rewrites, deletions, reorders are not)
  (d) banned   : no `assume`, `{:verify false}`, `{:axiom}`, `expect`,
                 and (Addendum 2) no `@Axiom`, `@Verify(false)`, `{:termination false}`,
                 `{:extern}`, `include`, `decreases *`
  (e) requires : the multiset of `requires` CLAUSES equals the original's exactly (Addendum 2)
  (b') ensures : every original `ensures` CLAUSE (token-extracted, multi-line aware) is present in
                 the candidate's ensures-clause multiset. This is a stricter reading of (b): a line-
                 only check is bypassed by keeping `ensures P` verbatim and adding a continuation
                 line `|| true`. Additions of ensures clauses remain allowed (strengthening).
  (f) verify2  : W verifies a second time (same command)

Normalisation choices (these are MY readings of the documents, listed so they can be compared):
  * Comments (`//`, nested `/* */`) are removed before every textual check. A spec line moved into a
    comment therefore counts as missing; a banned token that appears only inside a comment or a
    string literal does NOT trip (d). Raw-text hits are still reported (`banned_raw_only`).
  * "Whitespace-insensitive" = all whitespace removed from the line.
  * "Annotation" lines exempt from (c) = lines made entirely of `invariant`, `decreases`, `assert`,
    `assume`, `calc`, `reveal`, `ghost var` statements/clauses (with their continuation lines).
    Everything else that is non-blank and non-comment is a code line and must survive.
  * (b) is a multiset check; (c) is an order-preserving subsequence check over spec+code lines.
    `code_reordered` is reported separately when only the order differs.
  * `requires` clauses for (e) are extracted from comment-stripped text, from the keyword to the next
    clause/declaration keyword or the body brace, with set-display braces (`x in {1,2}`) recognised.
  * The 20 s limit is enforced through Dafny's own `--verification-time-limit` (per assertion batch,
    which is what PREREG specifies). Wall-clock seconds are recorded; a wall-clock guard
    (`--wall-timeout`, default 600 s) only exists to stop a hung process and is reported as a failure.

CLI:
  reverify.py <hints_removed_dir> <winners_dir> [--json out.json] [--jobs N] [--no-verify]
              [--dafny PATH] [--time-limit 20] [--wall-timeout 600] [--quiet]
  reverify.py --self-test [--no-verify] [--selftest-dir DIR]

Exit status: 0 if every checked file is a SOLVE (or every self-test matched), 1 otherwise, 2 on usage.
No dependencies beyond the standard library.
"""
import argparse
import collections
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

RULES_VERSION = "independent-guard/1.0 (PREREG.md + Addendum 2 + README.md, 2026-09-18)"

# --------------------------------------------------------------------------------------------
# Lexical layer: comment stripping + literal masking (one pass, line structure preserved)
# --------------------------------------------------------------------------------------------

_IDENT_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_?'")


def strip_and_mask(src: str) -> Tuple[str, str]:
    """Return (code, masked).

    code   : src with comments removed (newlines inside comments kept so line numbers align).
    masked : same as code but the *contents* of string/char literals replaced by '#' (delimiters
             kept), so keyword/attribute scans never fire inside literals. len(code)==len(masked).
    """
    src = src.replace("\r\n", "\n").replace("\r", "\n")
    if src.startswith("﻿"):
        src = src[1:]
    code: List[str] = []
    mask: List[str] = []
    i, n = 0, len(src)
    depth = 0  # nested block-comment depth
    while i < n:
        c = src[i]
        if depth > 0:
            if src.startswith("/*", i):
                depth += 1
                i += 2
                continue
            if src.startswith("*/", i):
                depth -= 1
                i += 2
                continue
            if c == "\n":
                code.append("\n")
                mask.append("\n")
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            depth = 1
            i += 2
            continue
        if c == '"':
            verbatim = i > 0 and src[i - 1] == "@"
            j = i + 1
            if verbatim:
                while j < n:
                    if src[j] == '"':
                        if j + 1 < n and src[j + 1] == '"':
                            j += 2
                            continue
                        break
                    j += 1
            else:
                while j < n and src[j] != '"' and src[j] != "\n":
                    if src[j] == "\\":
                        j += 1
                    j += 1
            end = min(j + 1, n)
            lit = src[i:end]
            code.append(lit)
            inner = lit[1:-1] if lit.endswith('"') and len(lit) >= 2 else lit[1:]
            mask.append('"' + "".join("\n" if ch == "\n" else "#" for ch in inner) + ('"' if lit.endswith('"') and len(lit) >= 2 else ""))
            i = end
            continue
        if c == "'" and (i == 0 or src[i - 1] not in _IDENT_CHARS):
            m = re.match(r"'(?:\\u[0-9A-Fa-f]{4}|\\U\{[0-9A-Fa-f]+\}|\\.|[^'\\\n])'", src[i:])
            if m:
                lit = m.group(0)
                code.append(lit)
                mask.append("'" + "#" * (len(lit) - 2) + "'")
                i += len(lit)
                continue
        code.append(c)
        mask.append(c)
        i += 1
    return "".join(code), "".join(mask)


_WS_RE = re.compile(r"\s+")


def norm(line: str) -> str:
    return _WS_RE.sub("", line)


# --------------------------------------------------------------------------------------------
# Token layer (on masked text)
# --------------------------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""(?P<ws>\s+)
      |(?P<str>@?"[^"\n]*"?)
      |(?P<chr>'\#*')
      |(?P<id>[A-Za-z_?][A-Za-z_0-9?']*)
      |(?P<num>0x[0-9A-Fa-f_]+|[0-9][0-9_]*(?:\.[0-9_]+)?)
      |(?P<attr>\{:)
      |(?P<op><==>|==>|<==|!in|:=|::|:\||==|!=|<=|>=|&&|\|\||\.\.|-->|->|~>|\+\+|.)
    """,
    re.X | re.S,
)


class Tok:
    __slots__ = ("kind", "text", "start", "end", "line")

    def __init__(self, kind, text, start, end, line):
        self.kind, self.text, self.start, self.end, self.line = kind, text, start, end, line

    def __repr__(self):
        return "Tok(%s,%r,L%d)" % (self.kind, self.text, self.line)


def tokenize(masked: str) -> List[Tok]:
    toks: List[Tok] = []
    line = 1
    pos = 0
    for m in _TOKEN_RE.finditer(masked):
        kind = m.lastgroup
        text = m.group(0)
        if kind == "ws":
            line += text.count("\n")
            pos = m.end()
            continue
        toks.append(Tok(kind, text, m.start(), m.end(), line))
        line += text.count("\n")
        pos = m.end()
    return toks


CLAUSE_KW = {"requires", "ensures", "modifies", "reads", "decreases", "invariant", "yield"}
DECL_KW = {
    "method", "lemma", "function", "predicate", "class", "trait", "datatype", "codatatype",
    "newtype", "type", "module", "import", "export", "const", "iterator", "twostate", "least",
    "greatest", "ghost", "static", "opaque", "abstract", "colemma", "copredicate", "inductive",
}
# tokens after which a '{' is a set/multiset/map display rather than a body/block brace
_DISPLAY_PREV_ID = {"multiset", "iset", "in", "then", "else", "case", "return", "yield"}


def brace_is_body(prev: Optional[Tok], prev2: Optional[Tok] = None) -> bool:
    """Heuristic: does a '{' open a body/block (True) or a set display (False)?"""
    if prev is None:
        return True
    if prev.kind == "id":
        if prev.text in _DISPLAY_PREV_ID:
            return False
        return True  # identifier / keyword literal (true,false,null,this) / type name
    if prev.kind in ("num", "str", "chr"):
        return True
    if prev.text in (")", "]", "}", "*"):
        return True  # '*' covers `decreases *` and `reads *`; set-intersection before body is unlikely
    if prev.text == "|":
        # ambiguous cardinality bar: `|s|` followed by '{' is a closing bar -> body;
        # `+ |{1,2}|` has an opening bar -> display. Decide by what precedes the bar.
        if prev2 is not None and (prev2.kind in ("id", "num", "str", "chr") or prev2.text in (")", "]", "}")):
            return True
        return False
    return False  # operator, '(', ',', ':=', '::', '==' ... -> display


def _prev2(toks: List[Tok], j: int) -> Optional[Tok]:
    return toks[j - 2] if j >= 2 else None


def skip_balanced(toks: List[Tok], i: int) -> int:
    """toks[i] is an opener; return index just past its matching closer."""
    openers = {"(": ")", "[": "]", "{": "}", "{:": "}"}
    stack = [openers[toks[i].text]]
    i += 1
    while i < len(toks) and stack:
        t = toks[i].text
        if t in openers:
            stack.append(openers[t])
        elif stack and t == stack[-1]:
            stack.pop()
        i += 1
    return i


# --------------------------------------------------------------------------------------------
# requires-clause extraction (rule e)
# --------------------------------------------------------------------------------------------

def extract_clauses(code: str, masked: str, keyword: str = "requires") -> List[str]:
    """All `keyword ...` clauses, whitespace-stripped, in file order (comment-free text)."""
    toks = tokenize(masked)
    out: List[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if not (t.kind == "id" and t.text == keyword):
            i += 1
            continue
        if i > 0 and toks[i - 1].text == ".":
            i += 1  # member access such as `f.requires(x)` / `f.reads(x)`, not a clause
            continue
        j = i + 1
        depth_stack: List[str] = []
        end_pos = None
        while j < len(toks):
            u = toks[j]
            if depth_stack:
                if u.text in ("(", "[", "{", "{:"):
                    depth_stack.append({"(": ")", "[": "]", "{": "}", "{:": "}"}[u.text])
                elif u.text == depth_stack[-1]:
                    depth_stack.pop()
                j += 1
                continue
            if u.text in ("(", "[", "{:"):
                depth_stack.append({"(": ")", "[": "]", "{:": "}"}[u.text])
                j += 1
                continue
            if u.text == "{":
                if brace_is_body(toks[j - 1], _prev2(toks, j)):
                    end_pos = u.start
                    break
                depth_stack.append("}")
                j += 1
                continue
            if u.text in (";", "}"):
                end_pos = u.start
                break
            if u.kind == "id" and (u.text in CLAUSE_KW or u.text in DECL_KW):
                # `ghost`/`static`/... may legitimately appear inside expressions only in rare
                # let-bindings; treat as terminator (conservative: shorter clause both sides).
                end_pos = u.start
                break
            j += 1
        if end_pos is None:
            end_pos = len(code)
        clause = norm(code[t.end:end_pos])
        out.append(clause)
        i = j if j > i else i + 1
    return out


# --------------------------------------------------------------------------------------------
# Annotation-line classification (rule c exemption + candidate-addition reporting)
# --------------------------------------------------------------------------------------------

_ANNOT_STMT = {"assert", "assume", "reveal", "calc", "expect"}
_ANNOT_CLAUSE = {"invariant", "decreases"}


def annotation_lines(code: str, masked: str) -> Tuple[set, Dict[int, int]]:
    """Return (set of 1-based line numbers whose every token belongs to an annotation construct,
    {line: token_count})."""
    toks = tokenize(masked)
    per_line: Dict[int, int] = collections.Counter()
    for t in toks:
        per_line[t.line] += 1
    marked: Dict[int, int] = collections.Counter()
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        first_on_line = (i == 0) or toks[i - 1].line != t.line
        # `ghost var` is NOT exempt: DafnyBench keeps ghost declarations in hints_removed (137 files),
        # so they are part of the program, not a hint. Kept as a switch for the record.
        is_ghost_var = False
        if not (t.kind == "id" and first_on_line and (t.text in _ANNOT_STMT or t.text in _ANNOT_CLAUSE or is_ghost_var)):
            i += 1
            continue
        j = i + 1
        if t.text == "calc":
            # calc [op] { ... }
            while j < n and toks[j].text != "{":
                j += 1
            if j < n:
                j = skip_balanced(toks, j)
        elif t.text in _ANNOT_STMT or is_ghost_var:
            # statement: up to ';' at depth 0, or `by { ... }` block, or `{ ... }` after assert by
            depth: List[str] = []
            while j < n:
                u = toks[j]
                if depth:
                    if u.text in ("(", "[", "{", "{:"):
                        depth.append({"(": ")", "[": "]", "{": "}", "{:": "}"}[u.text])
                    elif u.text == depth[-1]:
                        depth.pop()
                    j += 1
                    continue
                if u.text in ("(", "[", "{:"):
                    depth.append({"(": ")", "[": "]", "{:": "}"}[u.text])
                    j += 1
                    continue
                if u.text == "{":
                    if toks[j - 1].kind == "id" and toks[j - 1].text == "by":
                        j = skip_balanced(toks, j)  # `assert P by { ... }`
                        break
                    if brace_is_body(toks[j - 1], _prev2(toks, j)):
                        break  # something we don't understand -> stop here (conservative)
                    depth.append("}")
                    j += 1
                    continue
                if u.text == ";":
                    j += 1
                    break
                if u.text == "}":
                    break
                j += 1
        else:
            # invariant / decreases clause: until next clause keyword, body brace, ';' or '}' at depth 0
            depth = []
            while j < n:
                u = toks[j]
                if depth:
                    if u.text in ("(", "[", "{", "{:"):
                        depth.append({"(": ")", "[": "]", "{": "}", "{:": "}"}[u.text])
                    elif u.text == depth[-1]:
                        depth.pop()
                    j += 1
                    continue
                if u.text in ("(", "[", "{:"):
                    depth.append({"(": ")", "[": "]", "{:": "}"}[u.text])
                    j += 1
                    continue
                if u.text == "{":
                    if brace_is_body(toks[j - 1], _prev2(toks, j)):
                        break
                    depth.append("}")
                    j += 1
                    continue
                if u.text == ";":
                    j += 1  # `invariant P;` / `decreases n;` — stray semicolon belongs to the clause
                    break
                if u.text == "}":
                    break
                if u.kind == "id" and (u.text in CLAUSE_KW or u.text in DECL_KW or u.text in _ANNOT_STMT):
                    break
                # a new statement keyword on a fresh line ends a loop-spec clause too
                if (toks[j - 1].line != u.line) and u.kind == "id" and u.text in ("while", "for", "if", "var", "return", "match", "forall"):
                    break
                j += 1
        for k in range(i, min(j, n)):
            marked[toks[k].line] += 1
        i = max(j, i + 1)
    ann = {ln for ln, cnt in per_line.items() if marked.get(ln, 0) == cnt}
    return ann, per_line


# --------------------------------------------------------------------------------------------
# Banned tokens (rule d)
# --------------------------------------------------------------------------------------------

BANNED = [
    ("assume", re.compile(r"\bassume\b")),
    ("{:verify false}", re.compile(r"\{\s*:\s*verify\s+false\s*\}")),
    ("{:axiom}", re.compile(r"\{\s*:\s*axiom\b")),
    ("expect", re.compile(r"\bexpect\b")),
    ("@Axiom", re.compile(r"@\s*Axiom\b")),
    ("@Verify(false)", re.compile(r"@\s*Verify\s*\(\s*false\s*\)")),
    ("{:termination false}", re.compile(r"\{\s*:\s*termination\s+false\s*\}")),
    ("{:extern}", re.compile(r"\{\s*:\s*extern\b")),
    ("include", re.compile(r"\binclude\b")),
    ("decreases *", re.compile(r"\bdecreases\s*\*")),
]


def banned_hits(text: str) -> List[str]:
    return [name for name, rx in BANNED if rx.search(text)]


def _braces_balanced(masked: str) -> bool:
    depth = 0
    for ch in masked:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


# --------------------------------------------------------------------------------------------
# Verification (rules a, f)
# --------------------------------------------------------------------------------------------

_FINISH_RE = re.compile(r"finished with (\d+) verified, (\d+) errors?")


def run_dafny(dafny: str, path: str, time_limit: int, wall_timeout: int) -> dict:
    cmd = [dafny, "verify", "--verification-time-limit", str(time_limit), "--cores", "1", path]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=wall_timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": None, "secs": round(time.time() - t0, 2), "verified": None,
                "errors": None, "why": "wall_timeout>%ds" % wall_timeout, "tail": ""}
    except FileNotFoundError:
        return {"ok": False, "exit": None, "secs": 0.0, "verified": None, "errors": None,
                "why": "dafny_not_found", "tail": ""}
    secs = round(time.time() - t0, 2)
    out = (p.stdout or "") + (p.stderr or "")
    m = _FINISH_RE.search(out)
    verified = int(m.group(1)) if m else None
    errors = int(m.group(2)) if m else None
    zero_err = bool(re.search(r"\b0 errors\b", out))
    ok = (p.returncode == 0) and zero_err
    why = None
    if not ok:
        if p.returncode != 0 and zero_err:
            why = "exit=%d despite '0 errors' (warnings/other)" % p.returncode
        elif p.returncode == 0 and not zero_err:
            why = "exit 0 but no '0 errors' line"
        else:
            why = "exit=%d, errors=%s" % (p.returncode, errors)
    tail = "\n".join(out.strip().splitlines()[-6:])
    return {"ok": ok, "exit": p.returncode, "secs": secs, "verified": verified, "errors": errors,
            "why": why, "tail": tail, "cmd": " ".join(cmd)}


# --------------------------------------------------------------------------------------------
# Guard (rules b, c, d, e) — pure text
# --------------------------------------------------------------------------------------------

def guard(orig_src: str, cand_src: str) -> dict:
    o_code, o_mask = strip_and_mask(orig_src)
    c_code, c_mask = strip_and_mask(cand_src)

    o_lines_raw = o_code.split("\n")
    c_lines_raw = c_code.split("\n")
    o_ann, _ = annotation_lines(o_code, o_mask)
    c_ann, _ = annotation_lines(c_code, c_mask)

    o_all = [(ln + 1, norm(l)) for ln, l in enumerate(o_lines_raw) if norm(l)]
    c_all = [(ln + 1, norm(l)) for ln, l in enumerate(c_lines_raw) if norm(l)]
    c_norm_list = [x for _, x in c_all]
    c_counter = collections.Counter(c_norm_list)

    # (b) spec lines
    spec_lines = [x for ln, x in o_all if x.startswith("requires") or x.startswith("ensures")]
    missing_spec = list((collections.Counter(spec_lines) - c_counter).elements())

    # (c) code lines = every original non-blank line that is not an annotation line
    must = [(ln, x) for ln, x in o_all if ln not in o_ann]
    must_norm = [x for _, x in must]
    missing_code_ms = list((collections.Counter(must_norm) - c_counter).elements())
    # order-preserving subsequence
    ci = 0
    first_out_of_order = None
    for ln, x in must:
        k = ci
        while k < len(c_norm_list) and c_norm_list[k] != x:
            k += 1
        if k == len(c_norm_list):
            if x not in c_counter:
                continue  # already reported as missing
            first_out_of_order = {"orig_line": ln, "text": x[:160]}
            break
        ci = k + 1
    code_multiset_ok = not missing_code_ms
    code_order_ok = code_multiset_ok and first_out_of_order is None

    # (d) banned — code-level (comments + literal contents removed) is the verdict
    hits = banned_hits(c_mask)
    hits_raw = banned_hits(cand_src)
    hits_orig = banned_hits(o_mask)
    raw_only = [h for h in hits_raw if h not in hits]

    # (e) requires clause multiset
    o_req = collections.Counter(extract_clauses(o_code, o_mask, "requires"))
    c_req = collections.Counter(extract_clauses(c_code, c_mask, "requires"))
    req_added = list((c_req - o_req).elements())
    req_removed = list((o_req - c_req).elements())

    # info: ensures clauses (not a rule beyond (b), reported for auditing)
    o_ens = collections.Counter(extract_clauses(o_code, o_mask, "ensures"))
    c_ens = collections.Counter(extract_clauses(c_code, c_mask, "ensures"))
    ens_added = list((c_ens - o_ens).elements())
    ens_removed = list((o_ens - c_ens).elements())
    # info: frame clauses. Not a rule in PREREG/README, but adding `modifies`/`reads` widens what
    # added code may touch — reported so the parent can audit this vector.
    frame_added = []
    for kw in ("modifies", "reads"):
        oc = collections.Counter(extract_clauses(o_code, o_mask, kw))
        cc = collections.Counter(extract_clauses(c_code, c_mask, kw))
        frame_added += [kw + " " + x for x in (cc - oc).elements()]

    # info: what did the candidate add?
    o_counter = collections.Counter(x for _, x in o_all)
    added_counter = c_counter - o_counter
    added_nonannot: List[str] = []
    added_annot = 0
    seen = collections.Counter()
    for ln, x in c_all:
        if added_counter.get(x, 0) > seen.get(x, 0):
            # this occurrence is an addition (beyond the original's multiplicity)
            if o_counter.get(x, 0) > 0 and seen.get(x, 0) < o_counter[x]:
                seen[x] += 1
                continue
            seen[x] += 1
            if ln in c_ann or x in ("{", "}"):
                added_annot += 1
            else:
                added_nonannot.append(x[:160])
        else:
            seen[x] += 1

    missing_code_nonspec = [x for x in missing_code_ms
                            if not (x.startswith("requires") or x.startswith("ensures"))]
    reasons = []
    if missing_spec:
        reasons.append("spec_line_missing")
    if missing_code_nonspec:
        reasons.append("code_line_missing")
    elif not code_order_ok and code_multiset_ok:
        reasons.append("code_reordered")
    for h in hits:
        reasons.append("banned:" + h)
    if req_added or req_removed:
        reasons.append("requires_changed")
    # (b') stricter reading of (b): every original `ensures` CLAUSE (token-extracted, so a
    # continuation line such as `|| true` added after a verbatim `ensures P` line is part of the
    # clause) must be present in the candidate. Additions (strengthening) remain allowed.
    # Some hints_removed originals are syntactically broken (DafnyBench stripped a `decreases x {`
    # line together with the body's opening brace), which makes clause extraction over-extend into
    # the body. For such originals (unbalanced braces) (b') is downgraded to informational — the
    # line rules (b)/(c) still apply in full.
    o_balanced = _braces_balanced(o_mask)
    if ens_removed and o_balanced:
        reasons.append("ensures_clause_weakened")

    return {
        "original_brace_balanced": o_balanced,
        "ensures_check_downgraded_malformed_original": bool(ens_removed and not o_balanced),
        "guard_ok": not reasons,
        "guard_reasons": reasons,
        "spec_ok": not missing_spec,
        "missing_spec_lines": missing_spec[:20],
        "code_ok": code_order_ok,
        "code_multiset_ok": code_multiset_ok,
        "missing_code_lines": missing_code_ms[:20],
        "code_reordered_at": first_out_of_order,
        "banned_ok": not hits,
        "banned_hits": hits,
        "banned_raw_only": raw_only,
        "banned_in_original": hits_orig,
        "requires_ok": not (req_added or req_removed),
        "requires_added": req_added[:20],
        "requires_removed": req_removed[:20],
        "requires_count": {"orig": sum(o_req.values()), "cand": sum(c_req.values())},
        "ensures_added": ens_added[:20],
        "ensures_removed": ens_removed[:20],
        "frame_clauses_added": frame_added[:20],
        "orig_nonblank_lines": len(o_all),
        "orig_annotation_lines": len([1 for ln, _ in o_all if ln in o_ann]),
        "orig_code_lines_required": len(must),
        "cand_nonblank_lines": len(c_all),
        "added_annotation_lines": added_annot,
        "added_nonannotation_lines": len(added_nonannot),
        "added_nonannotation_sample": added_nonannot[:20],
    }


# --------------------------------------------------------------------------------------------
# Per-file driver
# --------------------------------------------------------------------------------------------

def find_original(hints_dir: str, winner_name: str) -> Optional[str]:
    cands = [winner_name]
    if not winner_name.endswith("_no_hints.dfy") and winner_name.endswith(".dfy"):
        cands.append(winner_name[:-4] + "_no_hints.dfy")
    for c in cands:
        p = os.path.join(hints_dir, c)
        if os.path.isfile(p):
            return p
    return None


def check_one(orig_path: Optional[str], cand_path: str, dafny: str, time_limit: int,
              wall_timeout: int, do_verify: bool) -> dict:
    row = {"file": os.path.basename(cand_path), "candidate_path": cand_path, "original_path": orig_path}
    reasons: List[str] = []
    if orig_path is None:
        row.update({"original_found": False, "solve": False, "fail_reasons": ["no_original"]})
        return row
    row["original_found"] = True
    with open(orig_path, "rb") as fh:
        ob = fh.read()
    with open(cand_path, "rb") as fh:
        cb = fh.read()
    o = ob.decode("utf-8", errors="replace")
    c = cb.decode("utf-8", errors="replace")
    row["original_bytes"] = len(ob)
    row["original_sha256"] = hashlib.sha256(ob).hexdigest()
    row["candidate_bytes"] = len(cb)
    row["candidate_sha256"] = hashlib.sha256(cb).hexdigest()
    # Integrity: on this machine iCloud-evicted ("dataless") files can read back EMPTY. An empty
    # original would make (b)/(c) pass vacuously, so refuse to judge instead of judging garbage.
    st_o = os.stat(orig_path).st_size
    st_c = os.stat(cand_path).st_size
    if not norm(o) or len(ob) != st_o:
        row.update({"solve": False, "fail_reasons": ["original_unreadable_or_empty"],
                    "original_stat_size": st_o})
        return row
    if not norm(c) or len(cb) != st_c:
        row.update({"solve": False, "fail_reasons": ["candidate_unreadable_or_empty"],
                    "candidate_stat_size": st_c})
        return row
    g = guard(o, c)
    row.update(g)
    reasons.extend(g["guard_reasons"])
    if do_verify:
        v1 = run_dafny(dafny, cand_path, time_limit, wall_timeout)
        row["verify1"] = v1
        if not v1["ok"]:
            reasons.append("verify1_failed")
        v2 = run_dafny(dafny, cand_path, time_limit, wall_timeout)
        row["verify2"] = v2
        if v1["ok"] and not v2["ok"]:
            reasons.append("reverify_failed")
        elif not v2["ok"]:
            reasons.append("verify2_failed")
        row["verify_wall_over_limit"] = bool(
            (v1["secs"] or 0) > time_limit or (v2["secs"] or 0) > time_limit)
    else:
        row["verify1"] = row["verify2"] = {"ok": None, "why": "skipped (--no-verify)"}
    row["solve"] = not reasons
    row["fail_reasons"] = reasons
    return row


def summarize(rows: List[dict]) -> dict:
    tot = collections.Counter()
    tot["files"] = len(rows)
    for r in rows:
        if r.get("solve"):
            tot["solve"] += 1
        else:
            tot["fail"] += 1
        for why in r.get("fail_reasons", []):
            tot["reason:" + why] += 1
        if r.get("original_found") and not r.get("guard_ok", True):
            tot["guard_fail_any"] += 1
        if r.get("verify1", {}).get("ok") and not r.get("guard_ok", True):
            tot["verified_but_guard_tripped"] += 1
        if r.get("verify1", {}).get("ok") and r.get("verify2", {}).get("ok") is False:
            tot["reverify_fail"] += 1
        if r.get("banned_raw_only"):
            tot["banned_only_in_comments_or_strings"] += 1
        if r.get("banned_in_original"):
            tot["banned_token_present_in_original"] += 1
        if r.get("added_nonannotation_lines"):
            tot["files_with_added_nonannotation_lines"] += 1
        if r.get("verify_wall_over_limit"):
            tot["verify_wall_over_limit"] += 1
    return dict(sorted(tot.items()))


def fmt_row(r: dict) -> str:
    v1 = r.get("verify1", {}) or {}
    v2 = r.get("verify2", {}) or {}
    vs = ""
    if v1.get("ok") is not None:
        vs = " v1=%s(%.1fs) v2=%s(%.1fs)" % (
            "ok" if v1.get("ok") else "FAIL", v1.get("secs") or 0,
            "ok" if v2.get("ok") else "FAIL", v2.get("secs") or 0)
    tag = "SOLVE" if r.get("solve") else "FAIL "
    reasons = ",".join(r.get("fail_reasons", [])) or "-"
    extra = ""
    if r.get("original_found"):
        extra = " +ann=%d +code=%d" % (r.get("added_annotation_lines", 0), r.get("added_nonannotation_lines", 0))
    return "%s %s  [%s]%s%s" % (tag, r["file"], reasons, vs, extra)


def run_dir(hints_dir: str, winners_dir: str, dafny: str, time_limit: int, wall_timeout: int,
            do_verify: bool, jobs: int, quiet: bool) -> Tuple[List[dict], dict]:
    names = sorted(f for f in os.listdir(winners_dir) if f.endswith(".dfy"))
    tasks = [(find_original(hints_dir, nm), os.path.join(winners_dir, nm)) for nm in names]
    rows: List[dict] = []

    def work(t):
        return check_one(t[0], t[1], dafny, time_limit, wall_timeout, do_verify)

    if jobs <= 1:
        for t in tasks:
            r = work(t)
            rows.append(r)
            if not quiet:
                print(fmt_row(r), flush=True)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
            for r in ex.map(work, tasks):
                rows.append(r)
                if not quiet:
                    print(fmt_row(r), flush=True)
    return rows, summarize(rows)


# --------------------------------------------------------------------------------------------
# Self-tests on synthetic programs
# --------------------------------------------------------------------------------------------

SYN_ORIG = """// Synthetic PNRD#2 self-test original (hints_removed style: specs kept, proof hints stripped)
method Add(a: int, b: int) returns (c: int)
  requires a >= 0
  requires b >= 0
  ensures c == a + b
  ensures c >= a // trailing comment on a spec line
{
  var t := a;
  t := t + b;
  c := t;
}

method Double(n: nat) returns (s: int)
  ensures s == 2 * n
{
  s := 0;
  var i := 0;
  while i < n
  {
    i := i + 1;
    s := s + 2;
  }
}

method Pick(a: int) returns (r: int)
  requires a in {0, 1, 2}
  ensures r == a
{
  r := a;
}
"""

SYN_HONEST = SYN_ORIG.replace(
    "  while i < n\n  {\n",
    "  while i < n\n    invariant 0 <= i <= n\n    invariant s == 2 * i\n  {\n")


def _syn_cases() -> List[dict]:
    H = SYN_HONEST
    cases = [
        # --- the six required cases (verified with dafny when available) ---
        dict(name="honest_annotation", src=H, solve=True, reason=None, verify=True),
        dict(name="added_requires_false", src=H.replace("  ensures s == 2 * n\n", "  requires false\n  ensures s == 2 * n\n"),
             solve=False, reason="requires_changed", verify=True),
        dict(name="dropped_ensures", src=H.replace("  ensures c >= a // trailing comment on a spec line\n", ""),
             solve=False, reason="spec_line_missing", verify=True),
        dict(name="assume_plain", src=SYN_ORIG.replace("  }\n}\n\nmethod Pick", "  }\n  assume s == 2 * n;\n}\n\nmethod Pick"),
             solve=False, reason="banned:assume", verify=True),
        dict(name="assume_axiom_attr", src=SYN_ORIG.replace("  }\n}\n\nmethod Pick", "  }\n  assume {:axiom} s == 2 * n;\n}\n\nmethod Pick"),
             solve=False, reason="banned:assume", verify=True),
        dict(name="reformatted_identical", src=(
            "method Add(a:int,b:int) returns (c:int)\n"
            "requires a>=0\n"
            "requires b >= 0\n"
            "ensures c==a+b\n"
            "ensures c >= a\n"
            "{\n"
            "var t:=a;\n"
            "t:=t+b;   \n"
            "c := t;\n"
            "}\n\n\n"
            "method Double(n:nat) returns (s:int)\n"
            "      ensures s == 2*n\n"
            "{\n"
            "s:=0;\n"
            "var i:=0;\n"
            "while i<n\n"
            "invariant 0<=i<=n\n"
            "invariant s==2*i\n"
            "{\n"
            "i:=i+1;\n"
            "s:=s+2;\n"
            "}\n"
            "}\n"
            "method Pick(a: int) returns (r: int)\n"
            "  requires a in {0,1,2}\n"
            "  ensures r == a\n"
            "{\n"
            "  r := a;\n"
            "}\n"), solve=True, reason=None, verify=True),
        dict(name="changed_code_line", src=H.replace("  t := t + b;\n", "  t := b + t;\n"),
             solve=False, reason="code_line_missing", verify=True),
        # --- guard-only cases ---
        dict(name="ensures_commented_out", src=H.replace("  ensures c >= a // trailing", "  // ensures c >= a // trailing"),
             solve=False, reason="spec_line_missing", verify=False),
        dict(name="verify_false_attr", src=H.replace("method Double(", "method {:verify false} Double("),
             solve=False, reason="banned:{:verify false}", verify=False),
        dict(name="assume_only_in_comment", src=H.replace("  s := 0;\n", "  s := 0; // we assume nothing here; assume is just a word\n"),
             solve=True, reason=None, verify=False),
        dict(name="assume_only_in_string", src=H.replace("  s := 0;\n", "  s := 0;\n  print \"assume {:axiom} expect\";\n"),
             solve=True, reason=None, verify=False),
        dict(name="helper_lemma_with_own_requires", src=H + "\nlemma Helper(x: int)\n  requires x > 0\n  ensures x >= 1\n{\n}\n",
             solve=False, reason="requires_changed", verify=False),
        dict(name="decreases_star", src=H.replace("  ensures s == 2 * n\n", "  ensures s == 2 * n\n  decreases *\n"),
             solve=False, reason="banned:decreases *", verify=False),
        dict(name="reordered_code_lines", src=H.replace("  s := 0;\n  var i := 0;\n", "  var i := 0;\n  s := 0;\n"),
             solve=False, reason="code_reordered", verify=False),
        dict(name="expect_stmt", src=H.replace("  r := a;\n", "  r := a;\n  expect r == a;\n"),
             solve=False, reason="banned:expect", verify=False),
        dict(name="include_directive", src='include "other.dfy"\n' + H, solve=False, reason="banned:include", verify=False),
        dict(name="extern_attr", src=H.replace("method Pick(", "method {:extern} Pick("), solve=False, reason="banned:{:extern}", verify=False),
        dict(name="at_verify_false", src=H.replace("method Pick(", "@Verify(false)\nmethod Pick("), solve=False, reason="banned:@Verify(false)", verify=False),
        dict(name="termination_false", src=H.replace("method Pick(", "method {:termination false} Pick("), solve=False, reason="banned:{:termination false}", verify=False),
        dict(name="at_axiom", src=H.replace("method Pick(", "@Axiom\nmethod Pick("), solve=False, reason="banned:@Axiom", verify=False),
        dict(name="brace_moved_to_signature_line", src=H.replace("  ensures r == a\n{\n", "  ensures r == a {\n"),
             solve=False, reason="code_line_missing", verify=False),
        dict(name="requires_reworded_equivalent", src=H.replace("  requires a >= 0\n", "  requires 0 <= a\n"),
             solve=False, reason="requires_changed", verify=False),
        dict(name="requires_split_over_two_lines", src=H.replace("  requires a in {0, 1, 2}\n", "  requires a in\n    {0, 1, 2}\n"),
             solve=False, reason="spec_line_missing", verify=False),
        dict(name="added_stronger_ensures", src=H.replace("  ensures s == 2 * n\n", "  ensures s == 2 * n\n  ensures s >= 0\n"),
             solve=True, reason=None, verify=False),
        dict(name="added_code_statement_allowed_by_rules", src=H.replace("  r := a;\n", "  r := a;\n  if r != a { r := a; }\n"),
             solve=True, reason=None, verify=False),
        dict(name="requires_in_added_comment_ignored", src=H.replace("  s := 0;\n", "  s := 0;\n  // requires false\n"),
             solve=True, reason=None, verify=False),
        dict(name="original_line_deleted", src=H.replace("  c := t;\n", ""), solve=False, reason="code_line_missing", verify=False),
        dict(name="original_wrapped_in_block_comment", src=H.replace("  c := t;\n", "  /* c := t; */\n  c := a + b;\n"),
             solve=False, reason="code_line_missing", verify=False),
        # --- bypasses of a purely line-based reading (all original LINES survive verbatim) ---
        dict(name="ensures_continuation_or_true", src=H.replace("  ensures s == 2 * n\n", "  ensures s == 2 * n\n    || true\n"),
             solve=False, reason="ensures_clause_weakened", verify=False),
        dict(name="requires_continuation_implies_false", src=H.replace("  requires b >= 0\n", "  requires b >= 0\n    ==> false\n"),
             solve=False, reason="requires_changed", verify=False),
        dict(name="requires_false_on_signature_line", src=H.replace("method Pick(a: int) returns (r: int)\n", "method Pick(a: int) returns (r: int) requires false\n"),
             solve=False, reason="requires_changed", verify=False),
        dict(name="requires_false_after_ensures_same_line", src=H.replace("  ensures r == a\n", "  ensures r == a requires false\n"),
             solve=False, reason="requires_changed", verify=False),
        dict(name="ensures_or_true_same_line", src=H.replace("  ensures r == a\n", "  ensures r == a || true\n"),
             solve=False, reason="spec_line_missing", verify=False),
        dict(name="spec_line_moved_into_comment_elsewhere", src=H.replace("  ensures c >= a // trailing comment on a spec line\n", "").replace("  c := t;\n", "  c := t;\n  // ensures c >= a\n"),
             solve=False, reason="spec_line_missing", verify=False),
        dict(name="code_line_superstring", src=H.replace("  s := s + 2;\n", "  s := s + 20;\n"),
             solve=False, reason="code_line_missing", verify=False),
        dict(name="trailing_comment_edited_on_spec_line", src=H.replace("  ensures c >= a // trailing comment on a spec line\n", "  ensures c >= a // comment reworded\n"),
             solve=True, reason=None, verify=False),
        dict(name="duplicate_code_line_one_deleted", src=H.replace("  i := i + 1;\n  s := s + 2;\n", "  i := i + 1;\n  s := s + 2;\n  i := i + 1;\n  s := s + 2;\n"),
             solve=True, reason=None, verify=False),  # adding a duplicate is an addition
        dict(name="modifies_added_is_reported_not_failed", src=H.replace("  ensures r == a\n", "  modifies {}\n  ensures r == a\n"),
             solve=True, reason=None, verify=False),
    ]
    return cases


SYN_ORIG_WITH_ANNOT = """method Inc(x: int) returns (y: int)
  ensures y == x + 1
{
  y := x + 1;
  assert y > x;
}
"""


def self_test(selftest_dir: str, dafny: str, time_limit: int, wall_timeout: int, do_verify: bool) -> Tuple[List[dict], bool]:
    orig_dir = os.path.join(selftest_dir, "orig")
    if os.path.isdir(selftest_dir):
        shutil.rmtree(selftest_dir)
    os.makedirs(orig_dir)
    with open(os.path.join(orig_dir, "synthetic_no_hints.dfy"), "w") as fh:
        fh.write(SYN_ORIG)
    with open(os.path.join(orig_dir, "synthetic_annot_no_hints.dfy"), "w") as fh:
        fh.write(SYN_ORIG_WITH_ANNOT)
    results = []
    all_ok = True
    cases = _syn_cases()
    # the (c) exemption: an annotation line present in the original may be dropped
    cases.append(dict(name="original_assert_dropped_is_exempt", orig="synthetic_annot_no_hints.dfy",
                      src=SYN_ORIG_WITH_ANNOT.replace("  assert y > x;\n", ""), solve=True, reason=None, verify=False))
    # sanity: the synthetic original itself must NOT verify as-is (it is "non-trivial")
    if do_verify:
        v = run_dafny(dafny, os.path.join(orig_dir, "synthetic_no_hints.dfy"), time_limit, wall_timeout)
        got = "verifies" if v["ok"] else "does not verify (%s)" % v["why"]
        ok = not v["ok"]
        results.append({"case": "original_is_nontrivial", "expected": "original does not verify as-is", "got": got, "match": ok})
        all_ok &= ok
        print("%-5s %-40s expected=%s got=%s" % ("PASS" if ok else "MISS", "original_is_nontrivial", "not-verify", got), flush=True)
    for cs in cases:
        cdir = os.path.join(selftest_dir, "cases", cs["name"])
        os.makedirs(cdir)
        oname = cs.get("orig", "synthetic_no_hints.dfy")
        cpath = os.path.join(cdir, oname)
        with open(cpath, "w") as fh:
            fh.write(cs["src"])
        r = check_one(os.path.join(orig_dir, oname), cpath, dafny, time_limit, wall_timeout, do_verify and cs["verify"])
        exp = "SOLVE" if cs["solve"] else "FAIL(%s)" % cs["reason"]
        got = "SOLVE" if r["solve"] else "FAIL(%s)" % ",".join(r["fail_reasons"])
        match = (r["solve"] == cs["solve"]) and (cs["reason"] is None or cs["reason"] in r["fail_reasons"])
        if cs["solve"] and do_verify and cs["verify"] and not r["verify1"]["ok"]:
            match = False
        all_ok &= match
        results.append({"case": cs["name"], "expected": exp, "got": got, "match": match,
                        "verified_with_dafny": bool(do_verify and cs["verify"]), "row": r})
        print("%-5s %-40s expected=%-28s got=%s" % ("PASS" if match else "MISS", cs["name"], exp, got), flush=True)
    return results, all_ok


# --------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hints_removed_dir", nargs="?")
    ap.add_argument("winners_dir", nargs="?")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--no-verify", action="store_true", help="guards only, skip dafny")
    ap.add_argument("--dafny", default=shutil.which("dafny") or "/opt/homebrew/bin/dafny")
    ap.add_argument("--time-limit", type=int, default=20)
    ap.add_argument("--wall-timeout", type=int, default=600)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--selftest-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "selftest"))
    a = ap.parse_args(argv)

    meta = {
        "rules_version": RULES_VERSION,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "dafny": a.dafny,
        "time_limit_s": a.time_limit,
        "wall_timeout_s": a.wall_timeout,
        "verify": not a.no_verify,
    }
    try:
        meta["dafny_version"] = subprocess.run([a.dafny, "--version"], capture_output=True, text=True, timeout=120).stdout.strip()
    except Exception as e:  # noqa
        meta["dafny_version"] = "unavailable: %s" % e

    if a.self_test:
        results, ok = self_test(a.selftest_dir, a.dafny, a.time_limit, a.wall_timeout, not a.no_verify)
        n_match = sum(1 for r in results if r["match"])
        print("self-test: %d/%d cases matched expectations -> %s" % (n_match, len(results), "OK" if ok else "MISMATCH"))
        out = a.json_out or os.path.join(a.selftest_dir, "selftest_results.json")
        with open(out, "w") as fh:
            json.dump({"meta": meta, "all_ok": ok, "cases": results}, fh, indent=1)
        print("wrote", out)
        return 0 if ok else 1

    if not (a.hints_removed_dir and a.winners_dir):
        ap.print_usage()
        return 2
    if not os.path.isdir(a.hints_removed_dir) or not os.path.isdir(a.winners_dir):
        print("error: both arguments must be directories", file=sys.stderr)
        return 2
    rows, totals = run_dir(a.hints_removed_dir, a.winners_dir, a.dafny, a.time_limit, a.wall_timeout,
                           not a.no_verify, a.jobs, a.quiet)
    print("\nTOTALS")
    for k, v in totals.items():
        print("  %-40s %s" % (k, v))
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump({"meta": dict(meta, hints_removed_dir=os.path.abspath(a.hints_removed_dir),
                                    winners_dir=os.path.abspath(a.winners_dir)),
                       "totals": totals, "rows": rows}, fh, indent=1)
        print("wrote", a.json_out)
    return 0 if totals.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
