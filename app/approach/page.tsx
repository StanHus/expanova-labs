import type { Metadata } from "next";
import Link from "next/link";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import Reveal from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Approach",
  description:
    "Verification-first AI. We ship intelligence you can check — graded by an objective oracle, not another model's opinion. A harness is only as good as its oracle, and we publish both sides of that law.",
};

const PRINCIPLES = [
  {
    n: "01",
    title: "Checked, not claimed.",
    body: "Most AI results ask you to trust a number. Ours hand you the receipt. When the gate is a mechanical check rather than a model's opinion, correctness stops being a promise and becomes something you can re-run.",
  },
  {
    n: "02",
    title: "A harness is only as good as its oracle.",
    body: "With a sound oracle, test-time compute buys large, trustworthy gains. With a weak or absent one, the very same machinery is neutral — or worse. We measured both, and we publish both.",
  },
  {
    n: "03",
    title: "Blocked beats faked.",
    body: "An honest “it didn’t pass” is worth more than a confident wrong answer. We report KILL verdicts next to the wins, because a lab that only shows you its hits isn’t showing you anything.",
  },
];

export default function Approach() {
  return (
    <div className="theme-dark" style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <Nav />
      <main className="flex-1">
        {/* HERO */}
        <section className="wide" style={{ paddingTop: "clamp(72px, 9vw, 140px)", paddingBottom: "clamp(40px, 5vw, 72px)" }}>
          <Reveal fade>
            <p className="eyebrow">Approach</p>
            <h1 style={{ maxWidth: "16ch", marginTop: "1.1rem" }}>We ship intelligence you can check.</h1>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.9375rem", color: "var(--muted)", maxWidth: "52ch", marginTop: "1.5rem", lineHeight: 1.7 }}>
              Not a benchmark to trust — a result you can re-run. Everything we build is graded by an
              objective oracle, not another model&rsquo;s opinion.
            </p>
          </Reveal>
        </section>

        <hr className="hairline" />

        {/* WHAT WE DELIVER */}
        <section className="wide" style={{ paddingBlock: "clamp(48px, 6vw, 80px)" }}>
          <Reveal fade>
            <p className="eyebrow">What we deliver</p>
            <p style={{ marginTop: "1.1rem", maxWidth: "30ch", fontFamily: "var(--font-display)", fontSize: "1.75rem", lineHeight: 1.25, letterSpacing: "-0.015em" }}>
              Systems where a verifier — not a model&rsquo;s say-so — decides what ships.
            </p>
            <p style={{ marginTop: "1.5rem", color: "var(--muted)", fontSize: "1.0625rem", lineHeight: 1.7, maxWidth: "58ch" }}>
              <strong style={{ color: "var(--text)" }}>PNRD#1</strong> proves the principle on mathematics: an open
              model lifted to 47% on miniF2F, every proof checked by the Lean kernel. We build the
              same <em>verifier-decides</em> mechanism into everything else — including multi-agent
              generation, where conflicts are resolved against ground truth (does the code actually
              support the claim?) rather than by an arbiter model&rsquo;s opinion. One thread:{" "}
              <strong style={{ color: "var(--text)" }}>replace judgment with verification.</strong>
            </p>
            <p style={{ marginTop: "1.5rem", color: "var(--muted)", fontSize: "0.9375rem", lineHeight: 1.7, maxWidth: "58ch", borderLeft: "2px solid var(--accent)", paddingLeft: "1rem" }}>
              A receipt, not a brag: when we wrapped a <em>cheap</em> model in a dense spec to test
              &ldquo;cheap&nbsp;→&nbsp;frontier,&rdquo; the spec alone shipped a <em>blank, broken</em>
              result. What made it work was the verification loop catching it and repairing against the
              real error — for about a cent. The verifier was the value, not the prompt. We publish the
              partial result too.
            </p>
          </Reveal>
        </section>

        <hr className="hairline" />

        {/* PRINCIPLES */}
        <section className="wide" style={{ paddingBlock: "clamp(48px, 6vw, 80px)" }}>
          <div style={{ display: "grid", gap: "clamp(40px, 5vw, 64px)" }}>
            {PRINCIPLES.map((p) => (
              <Reveal key={p.n} fade>
                <div style={{ display: "grid", gap: "0.5rem 2.5rem", gridTemplateColumns: "minmax(0,1fr)", maxWidth: "62ch" }}>
                  <span className="ill-label" style={{ color: "var(--accent-text)" }}>{p.n}</span>
                  <h2 style={{ maxWidth: "18ch" }}>{p.title}</h2>
                  <p style={{ marginTop: "0.5rem", color: "var(--muted)", fontSize: "1.0625rem", lineHeight: 1.7 }}>{p.body}</p>

                  {/* law comparison for principle 02 */}
                  {p.n === "02" && (
                    <div style={{ marginTop: "1.5rem", display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))" }}>
                      <div style={{ border: "1px solid var(--accent-border)", background: "var(--verified-bg)", borderRadius: "var(--radius)", padding: "1.1rem 1.25rem" }}>
                        <span className="verdict verdict--pass">✓ Sound oracle</span>
                        <p style={{ marginTop: "0.8rem", fontFamily: "var(--font-mono)", fontSize: "0.85rem", color: "var(--text)" }}>
                          Lean kernel · miniF2F<br />
                          <span style={{ color: "var(--accent-text)", fontWeight: 700 }}>24.6% → 47.1%</span> &nbsp;(+22.5 pts)
                        </p>
                      </div>
                      <div style={{ border: "1px solid var(--border-strong)", background: "var(--surface)", borderRadius: "var(--radius)", padding: "1.1rem 1.25rem" }}>
                        <span className="verdict verdict--kill">✗ Weak / no oracle</span>
                        <p style={{ marginTop: "0.8rem", fontFamily: "var(--font-mono)", fontSize: "0.85rem", color: "var(--muted)" }}>
                          self-graded / hidden tests<br />
                          <span style={{ color: "var(--faint)", fontWeight: 700 }}>≈ 0</span> &nbsp;— neutral to negative
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <hr className="hairline" />

        {/* THE BOUNDARY — where cheap+verified rivals frontier, and where it can't */}
        <section className="wide" style={{ paddingBlock: "clamp(48px, 6vw, 80px)" }}>
          <Reveal fade>
            <p className="eyebrow">The boundary</p>
            <h2 className="rule-verified" style={{ maxWidth: "22ch", marginTop: "1.1rem" }}>
              The law has two clauses — and the second is where we lose.
            </h2>
            <p className="dek" style={{ marginTop: "1.25rem", maxWidth: "48ch" }}>
              “A harness is only as good as its oracle” isn’t a slogan. Tightened, it’s a
              law with two clauses — and the honest half is the second one.
            </p>
            <p style={{ marginTop: "1.5rem", color: "var(--muted)", fontSize: "1.0625rem", lineHeight: 1.7, maxWidth: "58ch" }}>
              Our wrapper is a <em>selector</em>: it surfaces the best answer a cheap model already sampled. That
              is worth a lot in the right place and worth nothing in the wrong one. Here is the line, drawn both
              ways — because a lab that only shows you the side it wins on isn’t drawing a line, it’s
              selling one.
            </p>

            {/* WIN / LOSE 2-up */}
            <div style={{ marginTop: "2rem", display: "grid", gap: "1.25rem", gridTemplateColumns: "repeat(auto-fit, minmax(280px,1fr))" }}>
              {/* WINS */}
              <div style={{ border: "1px solid var(--accent-border)", background: "var(--verified-bg)", borderRadius: "var(--radius)", padding: "1.4rem 1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                <span className="verdict verdict--pass">✓ Where it wins</span>
                <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.65, color: "var(--text)", margin: 0 }}>
                  Work an <strong>external oracle</strong> can grade against the true objective:
                </p>
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.7rem" }}>
                  <li style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.6, color: "var(--text)", borderTop: "1px solid var(--accent-border)", paddingTop: "0.7rem" }}>
                    <strong style={{ color: "var(--accent-text)" }}>Formal proofs</strong> — checked by a
                    theorem-prover kernel. On miniF2F-test (244 problems), open gpt-oss-120b went{" "}
                    <strong style={{ color: "var(--accent-text)" }}>24.6% → 47.1%</strong>, every proof verified by
                    the Lean 4 kernel, false-positive rate exactly zero.
                  </li>
                  <li style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.6, color: "var(--text)", borderTop: "1px solid var(--accent-border)", paddingTop: "0.7rem" }}>
                    <strong style={{ color: "var(--accent-text)" }}>Spec-bound code</strong> — graded by a
                    compiler, a type-checker, or a held-out test suite that actually runs the answer. In our wrapper
                    test the loop — not the prompt — was load-bearing: it caught a blank, broken render a
                    dense spec alone had shipped and repaired it for ~1¢. (That test reached parity with a plain
                    one-shot — competent, not frontier; see the receipt below.)
                  </li>
                  <li style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.6, color: "var(--text)", borderTop: "1px solid var(--accent-border)", paddingTop: "0.7rem" }}>
                    <strong style={{ color: "var(--accent-text)" }}>Constraint-satisfying output</strong> —
                    structured results a schema or constraint validator can accept or reject mechanically.
                  </li>
                </ul>
              </div>

              {/* LOSES */}
              <div style={{ border: "1px solid var(--border-strong)", background: "var(--surface)", borderRadius: "var(--radius)", padding: "1.4rem 1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                <span className="verdict verdict--kill">✗ Where it loses</span>
                <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.65, color: "var(--text)", margin: 0 }}>
                  Work no sound oracle can grade — here the frontier model’s edge is irreducible:
                </p>
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.7rem" }}>
                  <li style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.6, color: "var(--muted)", borderTop: "1px solid var(--border-strong)", paddingTop: "0.7rem" }}>
                    <strong style={{ color: "var(--kill)" }}>Open-ended, creative, strategic, taste work</strong>{" "}
                    — the only available grader is an LLM judging another LLM, which is structurally
                    unreliable: over 50% error on JudgeBiasBench, plus self-preference, verbosity, and position
                    bias. You’re stuck at the cheap model’s <em>average</em> sample, and the frontier
                    model’s average is simply better.
                  </li>
                  <li style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.6, color: "var(--muted)", borderTop: "1px solid var(--border-strong)", paddingTop: "0.7rem" }}>
                    <strong style={{ color: "var(--kill)" }}>Tasks the answer is never sampled for</strong> —
                    if the correct answer isn’t in the cheap model’s N draws, no oracle can select it.
                    A selector can’t author what the model never produced. That coverage gap is exactly the
                    frontier model’s edge, and prompting cannot manufacture it.
                  </li>
                </ul>
              </div>
            </div>

            {/* THE REASON: the two conditions */}
            <p style={{ marginTop: "2rem", color: "var(--muted)", fontSize: "0.9375rem", lineHeight: 1.7, maxWidth: "62ch", borderLeft: "2px solid var(--accent)", paddingLeft: "1rem" }}>
              <strong style={{ color: "var(--text)" }}>Two gates, and both must open at once.</strong>{" "}
              <strong style={{ color: "var(--text)" }}>One:</strong>{" "}
              a sound, out-of-model oracle — a compiler, a held-out test suite, a prover kernel, a
              type-checker, a schema validator — that checks the <em>true</em> objective, never an LLM-judge
              and never a proxy. <strong style={{ color: "var(--text)" }}>Two:</strong> plausible coverage —
              the right answer sits within the cheap model’s sample support at feasible N, with real headroom,
              not a saturated benchmark. Best-of-N is upper-bounded by pass@k: it picks the best answer the model
              already sampled; it never adds one. Elicitation surfaces latent capability — it does not create it.
              Drop either gate and you fall back to the cheap model’s average, which the frontier model
              beats.
            </p>

            {/* HONESTY RECEIPT */}
            <p style={{ marginTop: "1.25rem", color: "var(--faint)", fontSize: "0.8125rem", lineHeight: 1.7, maxWidth: "62ch", fontFamily: "var(--font-mono)" }}>
              Receipt, both sides: the miniF2F lift above is real and re-runnable. A separate internal
              head-to-head (n = 40 slice, not a third-party benchmark — treat a few points as
              noise) had gpt-oss + harness top the <em>open</em> field at <strong style={{ color: "var(--muted)" }}>42.5%</strong> at
              low cost. And when we held the cheap model fixed to isolate the wrapper, the spec <em>alone</em>
              landed at parity with a plain one-shot — competent, not frontier. The load-bearing part was
              the verification loop, not the prompt. We have not shown cheap == frontier in general, and
              we’re not going to imply it.
            </p>

            {/* ONE-LINER CLOSE */}
            <p className="byline" style={{ marginTop: "2rem", maxWidth: "52ch", fontSize: "1.0625rem", lineHeight: 1.5, color: "var(--text)" }}>
              cheap + <span style={{ color: "var(--accent-text)" }}>verified</span> == frontier
              where a sound oracle exists and the answer is in reach;<br />
              cheap + <span style={{ color: "var(--kill)" }}>elicited</span> &lt; frontier
              everywhere else.
            </p>
          </Reveal>
        </section>

        <hr className="hairline" />

        {/* CLOSING */}
        <section className="wide" style={{ paddingBlock: "clamp(64px, 8vw, 112px)" }}>
          <Reveal fade>
            <h2 style={{ maxWidth: "20ch" }}>The proof of the approach is PNRD#1.</h2>
            <div style={{ marginTop: "1.75rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <Link className="btn btn--primary" href="/pnrd-1" style={{ background: "var(--accent)", borderColor: "var(--accent)", color: "#08130C" }}>
                Read PNRD#1 →
              </Link>
              <a className="btn btn--ghost" href="/data/pnrd1-minif2f-results.json">View the raw data</a>
            </div>
          </Reveal>
        </section>
      </main>
      <Footer />
    </div>
  );
}
