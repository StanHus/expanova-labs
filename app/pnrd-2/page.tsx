import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import Reveal from "@/components/Reveal";
import { OracleLift, PassAtK, BudgetSplit, type OracleRow } from "@/components/Charts2";

export const metadata: Metadata = {
  title: "PNRD#2",
  description:
    "PNRD#2 tests the law a second time: the same sample-check-repair harness, the same open model, a second sound oracle — the Dafny verifier on DafnyBench. Pre-registered gate, published harness, every number read from the result file.",
};

/* ----------------------------- data, read at build ----------------------------- */
type Pnrd1 = { n: number; rows: Record<string, { arm_a: boolean; arm_b: boolean; b_at: number; compiles: number }> };
type Arm0 = { n: number; trivial: number; limit_s: number; rows: Record<string, boolean> };
type Run = {
  benchmark: string; oracle: string; n: number; BON: number; REPAIR: number; fewshot: boolean;
  models: { general: string; provider: string }; a_only: number; b_only: number;
  pass_at_k: Record<string, number>; kernel_checks: number; checks_on_unsolved: number;
  guard_fails: number; reverify_failed: number; errors: number; tokens_in: number; tokens_out: number;
  price_per_M: [number, number]; cost_usd: number; cost_per_problem_usd: number; cost_per_b_solve_usd: number | null;
  wall_secs: number; rows: Record<string, { arm_a: boolean; arm_b: boolean; b_at: number; compiles: number; guard_fail: number }>;
};

function readJson<T>(rel: string): T | null {
  try { return JSON.parse(fs.readFileSync(path.join(/*turbopackIgnore: true*/ process.cwd(),rel), "utf8")) as T; } catch { return null; }
}
function listRuns(): { file: string; run: Run }[] {
  const dir = path.join(/*turbopackIgnore: true*/ process.cwd(),"public/data/pnrd2");
  let files: string[] = [];
  try { files = fs.readdirSync(dir).filter((f) => f.startsWith("run-") && f.endsWith(".json")).sort(); } catch { /* none */ }
  return files.map((f) => ({ file: f, run: JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) as Run }));
}

const PREREG_COMMIT = "112a544";
const PREREG_TIME = "2026-09-18 11:59 CEST";

function Section({ eyebrow, title, lead, children, id }: {
  eyebrow: string; title: string; lead?: string; children?: React.ReactNode; id?: string;
}) {
  return (
    <section id={id} style={{ scrollMarginTop: "80px" }}>
      <Reveal fade>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="rule-verified" style={{ marginTop: "0.6rem" }}>{title}</h2>
        {lead && <p className="dek" style={{ marginTop: "1.1rem", maxWidth: "44ch" }}>{lead}</p>}
      </Reveal>
      {children}
    </section>
  );
}
const Box = ({ children, maxWidth }: { children: React.ReactNode; maxWidth?: number }) => (
  <div style={{ marginTop: "1.75rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "1.75rem 1.5rem 1.25rem", maxWidth }}>{children}</div>
);
const pct = (a: number, n: number) => ((100 * a) / n).toFixed(1) + "%";

export default function PNRD2() {
  const p1 = readJson<Pnrd1>("public/data/pnrd1-minif2f-results.json");
  const arm0 = readJson<Arm0>("public/data/pnrd2/arm0-trivial.json");
  const runs = listRuns();
  const ran = runs.length > 0;

  // PNRD#1 derived series (never typed by hand)
  const p1rows = p1 ? Object.values(p1.rows) : [];
  const p1n = p1?.n ?? 0;
  const p1a = p1rows.filter((r) => r.arm_a).length, p1b = p1rows.filter((r) => r.arm_b).length;
  const p1curve = Array.from({ length: 16 }, (_, i) => p1rows.filter((r) => r.arm_b && r.b_at > 0 && r.b_at <= i + 1).length);
  const p1checks = p1rows.reduce((s, r) => s + r.compiles, 0);
  const p1waste = p1rows.filter((r) => !r.arm_b).reduce((s, r) => s + r.compiles, 0);

  const oracleRows: OracleRow[] = [
    { label: "PNRD#1 · Lean 4 kernel · miniF2F-test", model: "gpt-oss-120b", n: p1n, oneShot: p1a, harness: p1b },
    ...runs.map(({ run }) => ({
      label: `PNRD#2 · Dafny verifier · DafnyBench${run.n < 700 ? ` (${run.n}-program slice)` : ""}`,
      model: run.models.general.split("/").pop() ?? run.models.general, n: run.n, oneShot: run.a_only, harness: run.b_only,
    })),
    ...(runs.some(({ run }) => run.models.general.includes("gpt-oss-120b")) ? [] :
      [{ label: "PNRD#2 · Dafny verifier · DafnyBench — primary arm", model: "gpt-oss-120b", n: 781, oneShot: 0, harness: 0, pending: true }]),
  ];

  // per-run derived facts for the pre-registration scorecard
  const scored = runs.map(({ run }) => {
    const ids = Object.keys(run.rows);
    const nontriv = ids.filter((id) => !(arm0?.rows[id] ?? false));
    const a = nontriv.filter((id) => run.rows[id].arm_a).length, b = nontriv.filter((id) => run.rows[id].arm_b).length;
    const lift = nontriv.length ? (100 * (b - a)) / nontriv.length : 0;
    const by8 = run.pass_at_k["8"] ?? 0, total = run.b_only || 1;
    const sat = (100 * by8) / total;
    const waste = (100 * run.checks_on_unsolved) / Math.max(1, run.kernel_checks);
    return { run, nontriv: nontriv.length, a, b, lift, sat, waste, guard: run.guard_fails };
  });

  return (
    <>
      <Nav />
      <main className="flex-1">
        <div style={{ maxWidth: 880, marginInline: "auto", paddingInline: "var(--gutter)" }}>
          <header style={{ paddingTop: "clamp(48px, 6vw, 84px)", paddingBottom: "1.5rem", maxWidth: "22ch" }}>
            <Reveal fade>
              <p className="eyebrow">Research · September 2026 · pre-registered</p>
              <h1 style={{ marginTop: "0.9rem" }}>PNRD#2: the law, tested twice</h1>
            </Reveal>
          </header>
          <Reveal fade>
            <p className="dek" style={{ maxWidth: "54ch" }}>
              <Link href="/pnrd-1">PNRD#1</Link> proved it once: a cheap open model plus a sound oracle nearly doubled its
              verified solve rate. PNRD#2 keeps the harness and the model and changes only the oracle — from the Lean&nbsp;4
              kernel to the <em>Dafny verifier</em>. If the lift reproduces, &ldquo;a harness is only as good as its
              oracle&rdquo; is a law. If it doesn&rsquo;t, that is the result.
            </p>
            <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
              <span className="byline">By Expanova Labs</span>
              {ran ? <span className="verdict verdict--pass">✓ Verifier-checked</span>
                   : <span className="verdict verdict--kill">registered · not yet run</span>}
              <span className="byline">gate fixed in commit {PREREG_COMMIT} · {PREREG_TIME}</span>
            </div>
          </Reveal>

          {/* ---------------- STATUS / HEADLINE ---------------- */}
          <Reveal fade>
            <figure style={{ margin: "2.75rem 0 0", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "clamp(1.5rem, 3vw, 2.25rem)", display: "grid", gap: "1.5rem" }}>
              {ran ? scored.map(({ run, lift, nontriv, a, b }) => (
                <div key={run.models.general}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "0.5ch", flexWrap: "wrap", lineHeight: 1 }}>
                    <span className="bignum" style={{ fontSize: "clamp(2.4rem,1.6rem+3vw,3.6rem)", color: "var(--muted)" }}>{pct(run.a_only, run.n)}</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "clamp(1.6rem,1rem+2vw,2.4rem)", color: "var(--faint)", padding: "0 0.2ch" }}>→</span>
                    <span className="bignum" style={{ fontSize: "clamp(2.4rem,1.6rem+3vw,3.6rem)", color: "var(--accent-text)" }}>{pct(run.b_only, run.n)}</span>
                  </div>
                  <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
                    <span className="receipt">verifier-checked · {run.b_only} / {run.n}</span>
                    <span className="byline">{run.models.general.split("/").pop()} · best-of-{run.BON} + {run.REPAIR} repair{run.fewshot ? " + few-shot" : ""} · {run.guard_fails} guard trips</span>
                  </div>
                  <p className="byline" style={{ marginTop: "0.9rem" }}>
                    Non-trivial subset ({nontriv} programs that do not verify with zero hints): {pct(a, nontriv)} → {pct(b, nontriv)}, {lift >= 0 ? "+" : ""}{lift.toFixed(1)} pts.
                  </p>
                </div>
              )) : (
                <div>
                  <p style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.5rem", lineHeight: 1.3, letterSpacing: "-0.01em" }}>
                    The gate is fixed. The harness is published. The run has not happened.
                  </p>
                  <p className="byline" style={{ marginTop: "0.9rem", lineHeight: 1.7, maxWidth: "62ch" }}>
                    Blocked beats faked, so this page ships in its registered state. The primary arm needs the same open model
                    as PNRD#1 (gpt-oss-120b) on a personal key; none on the lab machine reaches it. The pilot arm (a cheap closed
                    model) hit a free-tier quota of 20 requests per day before completing a single program. When a run lands,
                    only the data file changes; every number on this page is read from it.
                  </p>
                </div>
              )}
              {arm0 && (
                <p className="byline" style={{ margin: 0, borderTop: "1px solid var(--border)", paddingTop: "1rem" }}>
                  Arm 0, no model: <strong style={{ color: "var(--text)" }}>{arm0.trivial} of {arm0.n}</strong> stripped programs ({pct(arm0.trivial, arm0.n)}) already
                  verify with zero hints. They are reported, and the lift is also given without them.
                </p>
              )}
            </figure>
          </Reveal>

          <div className="stack-lg" style={{ paddingTop: "clamp(56px, 7vw, 96px)", paddingBottom: "clamp(64px, 8vw, 104px)" }}>
            {/* ---------------- SAME HARNESS, NEW ORACLE ---------------- */}
            <Section id="design" eyebrow="What changed, what didn't"
              title="Same harness. Same model. Second oracle."
              lead="Everything that produced PNRD#1's lift is held fixed except the judge. The Dafny verifier replaces the Lean kernel; DafnyBench's 782 stripped programs replace miniF2F's 244 theorems.">
              <Reveal fade>
                <div style={{ marginTop: "1.75rem" }}>
                  <table className="bench">
                    <thead><tr><th scope="col">Component</th><th scope="col">PNRD#1</th><th scope="col">PNRD#2</th></tr></thead>
                    <tbody>
                      <tr><th scope="row" style={{ fontWeight: 400 }}>Oracle</th><td>Lean 4 kernel v4.31.0</td><td>Dafny verifier 4.11.0, 20 s per check</td></tr>
                      <tr><th scope="row" style={{ fontWeight: 400 }}>Task</th><td>Prove the theorem</td><td>Restore the annotations so the program verifies; specs and code untouched</td></tr>
                      <tr><th scope="row" style={{ fontWeight: 400 }}>Harness</th><td>best-of-16 · repair · few-shot</td><td>best-of-16 · repair · few-shot (one held-out example)</td></tr>
                      <tr><th scope="row" style={{ fontWeight: 400 }}>Model</th><td>gpt-oss-120b, open weights</td><td>gpt-oss-120b, open weights (primary arm)</td></tr>
                      <tr><th scope="row" style={{ fontWeight: 400 }}>Cheat guard</th><td>Kernel accepts no <code>sorry</code>; statements fixed</td><td>Every original spec and code line must survive; no <code>assume</code>, <code>{"{:verify false}"}</code>, <code>{"{:axiom}"}</code>; winners verified twice</td></tr>
                      <tr><th scope="row" style={{ fontWeight: 400 }}>Gate</th><td>Written after the run</td><td>Written before the run, commit {PREREG_COMMIT}</td></tr>
                    </tbody>
                    <caption>The last row is the methodological step up. PNRD#1&rsquo;s numbers were honest; PNRD#2&rsquo;s were promised first.</caption>
                  </table>
                </div>
              </Reveal>
            </Section>

            {/* ---------------- THE LAW, PER ORACLE ---------------- */}
            <Section id="law" eyebrow="The law, per oracle" title="One mechanism, two judges."
              lead="Each row is the same shape: grey is the model alone, green is the model with a verifier deciding what ships. A second green bar that clears its grey bar is the law holding.">
              <Reveal fade><Box><OracleLift rows={oracleRows} /></Box></Reveal>
            </Section>

            {/* ---------------- SATURATION ---------------- */}
            <Section id="saturation" eyebrow="The second gate" title="Where sampling stops paying."
              lead="Best-of-N can only surface an answer the model already sampled. The curve shows how fast that support is exhausted. PNRD#1 landed 95% of its solves by attempt 8.">
              <Reveal fade>
                <Box>
                  <PassAtK n={p1n} maxK={16} series={[
                    { label: "PNRD#1 · Lean", counts: p1curve, primary: !ran },
                  ]} />
                  {ran && scored.map(({ run }) => (
                    <div key={run.models.general} style={{ marginTop: "1.5rem", borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                      <PassAtK n={run.n} maxK={run.BON} series={[
                        { label: `PNRD#2 · Dafny · ${run.models.general.split("/").pop()}`, counts: Array.from({ length: run.BON }, (_, i) => run.pass_at_k[String(i + 1)] ?? 0), primary: true },
                      ]} />
                    </div>
                  ))}
                  {!ran && <p className="byline" style={{ marginTop: "1rem" }}>PNRD#2&rsquo;s curve is drawn here from <code>pass_at_k</code> in the result file once a run exists.</p>}
                </Box>
              </Reveal>
            </Section>

            {/* ---------------- BUDGET ---------------- */}
            <Section id="budget" eyebrow="Where the compute went" title="Most checks are spent on what never solves."
              lead="This is the number the harness should be judged on next. A selector that keeps sampling a theorem it will never reach is paying for nothing, and it is most of the bill.">
              <Reveal fade>
                <Box>
                  <BudgetSplit rows={[
                    { label: "PNRD#1 · Lean kernel checks", total: p1checks, onUnsolved: p1waste },
                    ...scored.map(({ run }) => ({ label: `PNRD#2 · Dafny checks · ${run.models.general.split("/").pop()}`, total: run.kernel_checks, onUnsolved: run.checks_on_unsolved })),
                  ]} />
                  {ran && scored.map(({ run }) => (
                    <p key={run.models.general} className="byline" style={{ marginTop: "1rem", lineHeight: 1.7 }}>
                      {run.models.general.split("/").pop()}: {run.tokens_in.toLocaleString()} tokens in, {run.tokens_out.toLocaleString()} out,
                      ${run.cost_usd.toFixed(2)} total at ${run.price_per_M[0]}/${run.price_per_M[1]} per million ·
                      ${run.cost_per_problem_usd.toFixed(3)} per program{run.cost_per_b_solve_usd ? ` · $${run.cost_per_b_solve_usd.toFixed(3)} per verified solve` : ""} · {Math.round(run.wall_secs / 60)} min wall.
                    </p>
                  ))}
                </Box>
              </Reveal>
            </Section>

            {/* ---------------- PRE-REGISTRATION SCORECARD ---------------- */}
            <Section id="prereg" eyebrow="Pre-registration" title="Promised first, then measured."
              lead={`Four predictions and a three-way gate were committed at ${PREREG_TIME} before any harness result existed. Each is scored here from the result file, not by hand.`}>
              <Reveal fade>
                <div style={{ marginTop: "1.75rem" }}>
                  <table className="bench">
                    <thead><tr><th scope="col" style={{ width: 26 }} aria-label="status" /><th scope="col">Prediction</th><th scope="col" style={{ textAlign: "right" }}>Threshold</th><th scope="col" style={{ textAlign: "right" }}>Measured</th></tr></thead>
                    <tbody>
                      {[
                        { k: "Lift on the non-trivial subset", th: "≥ +10 pts", val: (s: typeof scored[number]) => `${s.lift >= 0 ? "+" : ""}${s.lift.toFixed(1)} pts`, ok: (s: typeof scored[number]) => s.lift >= 10 },
                        { k: "Solves landing by attempt 8", th: "≥ 80%", val: (s: typeof scored[number]) => `${s.sat.toFixed(0)}%`, ok: (s: typeof scored[number]) => s.sat >= 80 },
                        { k: "Checks spent on never-solved programs", th: "≥ 70%", val: (s: typeof scored[number]) => `${s.waste.toFixed(0)}%`, ok: (s: typeof scored[number]) => s.waste >= 70 },
                        { k: "Guard trips (verified but spec-weakening)", th: "> 0", val: (s: typeof scored[number]) => `${s.guard}`, ok: (s: typeof scored[number]) => s.guard > 0 },
                      ].map((row) => (
                        <tr key={row.k}>
                          <td aria-hidden style={{ color: ran ? (scored.every(row.ok) ? "var(--verified)" : "var(--kill)") : "var(--faint)" }}>{ran ? (scored.every(row.ok) ? "✓" : "✗") : "·"}</td>
                          <th scope="row" style={{ fontWeight: 400 }}>{row.k}</th>
                          <td className="num">{row.th}</td>
                          <td className="num">{ran ? scored.map((s) => row.val(s)).join(" · ") : "not run"}</td>
                        </tr>
                      ))}
                    </tbody>
                    <caption>
                      Gate: SHIP if lift ≥ +10 with guard trips reported and zero unguarded false positives · PARTIAL at +5 to +10 · KILL below +5, or any winner failing re-verification, or a bypassable guard. Full text: <code>harness/pnrd2/PREREG.md</code>.
                    </caption>
                  </table>
                </div>
              </Reveal>
            </Section>

            {/* ---------------- HONEST CEILING ---------------- */}
            <Section eyebrow="The honest ceiling" title="What this can and cannot show.">
              <Reveal fade>
                <ul className="prose" style={{ marginTop: "1.75rem", maxWidth: "58ch" }}>
                  <li><strong>Annotation is easier than proof.</strong> DafnyBench&rsquo;s own protocol already includes error feedback, and {arm0 ? `${pct(arm0.trivial, arm0.n)} of` : "a fifth of"} the stripped programs verify with no hints at all. The claim under test is not &ldquo;Dafny is hard&rdquo;; it is that the <em>same harness shape</em> yields a <em>verified</em> lift on a second sound oracle, with its cost accounted per check.</li>
                  <li><strong>The model is the control.</strong> Only the primary arm, gpt-oss-120b, isolates the oracle. Any other model reported here is a separate row and never blended into the headline.</li>
                  <li><strong>A verifier time limit is a choice.</strong> 20 seconds per check. A proof that needs 21 counts as a miss. The limit is in the result file.</li>
                  <li><strong>Registered follow-up, not run:</strong> Ternary-Bonsai-2-27B locally (≈1.7 bits per weight), where N is bounded by wall-clock instead of dollars. Blocked by disk on the lab machine, not by design.</li>
                </ul>
              </Reveal>
            </Section>

            <Reveal fade>
              <p className="byline" style={{ lineHeight: 1.7 }}>
                Reproducible: <a href="https://github.com/StanHus/expanova-labs/tree/pnrd-2/harness/pnrd2">harness, guards and pre-registration on GitHub</a> ·
                DafnyBench <code>hints_removed</code> · Dafny 4.11.0 ·{" "}
                <a href="/data/pnrd2/arm0-trivial.json">arm 0 data →</a>
                {runs.map(({ file }) => <span key={file}> · <a href={`/data/pnrd2/${file}`}>{file} →</a></span>)}
              </p>
            </Reveal>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
