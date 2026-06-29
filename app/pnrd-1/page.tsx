import type { Metadata } from "next";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import Reveal from "@/components/Reveal";
import { HeadlineStat, LiftChart, FamilyChart, HeadToHead } from "@/components/Charts";
import { HarnessFlow, OracleGate } from "@/components/Illustrations";

export const metadata: Metadata = {
  title: "Introducing PNRD#1",
  description:
    "PNRD#1 wraps an open model and proves its work. On miniF2F it nearly doubled the solve rate — 24.6% to 47.1% — and every proof is checked by the Lean 4 kernel, so the false-positive rate is exactly zero.",
};

function Section({
  eyebrow, title, lead, children, id,
}: {
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

export default function PNRD1() {
  return (
    <>
      <Nav />
      <main className="flex-1">
        <div style={{ maxWidth: 880, marginInline: "auto", paddingInline: "var(--gutter)" }}>
          {/* ---------------- HEADER ---------------- */}
          <header style={{ paddingTop: "clamp(48px, 6vw, 84px)", paddingBottom: "1.5rem", maxWidth: "20ch" }}>
            <Reveal fade>
              <p className="eyebrow">Research · June 2026</p>
              <h1 style={{ marginTop: "0.9rem" }}>Introducing PNRD#1</h1>
            </Reveal>
          </header>
          <Reveal fade>
            <p className="dek" style={{ maxWidth: "52ch" }}>
              PNRD#1 wraps an open model and makes it <em>prove its work</em>. On miniF2F it nearly
              doubled the solve rate — and every proof is machine-checked, so you don&rsquo;t have to
              take our word for it.
            </p>
            <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
              <span className="byline">By Expanova Labs</span>
              <span className="verdict verdict--pass">✓ Kernel-verified</span>
            </div>
          </Reveal>

          {/* ---------------- HERO STAT + LIFT ---------------- */}
          <Reveal fade>
            <figure
              style={{
                margin: "2.75rem 0 0", background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: "var(--radius)", padding: "clamp(1.5rem, 3vw, 2.25rem)",
                display: "grid", gap: "2rem", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", alignItems: "center",
              }}
            >
              <div>
                <HeadlineStat />
                <p className="byline" style={{ marginTop: "1.1rem" }}>
                  miniF2F-test · 244 Lean 4 theorems · gpt-oss-120b (open weights)
                </p>
              </div>
              <LiftChart />
            </figure>
          </Reveal>

          <div className="stack-lg" style={{ paddingTop: "clamp(56px, 7vw, 96px)", paddingBottom: "clamp(64px, 8vw, 104px)" }}>
            {/* ---------------- HOW IT WORKS ---------------- */}
            <Section
              id="method"
              eyebrow="How it works"
              title="Sample. Check. Repair. Repeat."
              lead="The model writes many proofs. The Lean 4 kernel checks each one. Failures come back with the exact error to fix. The first that compiles wins — nothing else ships."
            >
              <Reveal fade>
                <div style={{ marginTop: "2rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "1.75rem 1.5rem 1.25rem" }}>
                  <HarnessFlow />
                </div>
              </Reveal>
            </Section>

            {/* ---------------- PERFECT JUDGE ---------------- */}
            <Section
              eyebrow="Why you can trust it"
              title="The grader is a kernel, not an LLM."
              lead="A proof passes only if the Lean kernel compiles it with no shortcuts — there is no model to talk into a yes. A wrong proof can't be bluffed past it; a false positive would take a mis-stated theorem or a kernel bug, not a convincing-looking proof."
            >
              <Reveal fade>
                <div style={{ marginTop: "2rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "1.75rem 1.5rem 1.25rem", maxWidth: 600 }}>
                  <OracleGate />
                </div>
              </Reveal>
            </Section>

            {/* ---------------- RESULT ---------------- */}
            <Section id="results" eyebrow="The result" title="One open model, nearly twice the proofs.">
              <Reveal fade>
                <div style={{ marginTop: "1.75rem" }}>
                  <table className="bench">
                    <thead>
                      <tr>
                        <th scope="col" style={{ width: 26 }} aria-label="verified" />
                        <th scope="col">Configuration</th>
                        <th scope="col" style={{ textAlign: "right" }}>Solved / 244</th>
                        <th scope="col" style={{ textAlign: "right" }}>Pass rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="glyph-pass" aria-hidden>✓</td>
                        <th scope="row" style={{ fontWeight: 400 }}>One-shot baseline</th>
                        <td className="num">60</td>
                        <td className="num">24.6%</td>
                      </tr>
                      <tr>
                        <td className="glyph-pass" aria-hidden>✓</td>
                        <th scope="row" style={{ fontWeight: 400 }}>PNRD#1 · best-of-8, no few-shot</th>
                        <td className="num">93</td>
                        <td className="num">38.1%</td>
                      </tr>
                      <tr data-highlight="true">
                        <td className="glyph-pass" aria-hidden>✓</td>
                        <th scope="row" style={{ fontWeight: 600 }}>PNRD#1 · best-of-16 + repair + few-shot</th>
                        <td className="num" style={{ fontWeight: 600 }}>115</td>
                        <td className="num" style={{ fontWeight: 600, color: "var(--accent-text)" }}>47.1%</td>
                      </tr>
                    </tbody>
                    <caption>Same open model on every row · ✓ each solve checked by Lean 4 kernel v4.31.0</caption>
                  </table>
                </div>
              </Reveal>
              <Reveal fade>
                <p className="dek" style={{ marginTop: "2.5rem", maxWidth: "44ch" }}>
                  The lift is real and uneven. We solved more of everything — and stayed honest about
                  the hard tail.
                </p>
                <div style={{ marginTop: "1.5rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "1.75rem 1.5rem 1.25rem" }}>
                  <FamilyChart />
                </div>
              </Reveal>
            </Section>

            {/* ---------------- HEAD-TO-HEAD ---------------- */}
            <Section eyebrow="Verified head-to-head" title="Cheap + verified vs. the field.">
              <Reveal fade>
                <p className="dek" style={{ marginTop: "1.1rem", maxWidth: "48ch" }}>
                  Same 40 miniF2F problems, every proof kernel-checked. A cheap open model + our
                  harness tops the verified board — and one-shot gpt-oss costs a fraction of the
                  frontier-open models per problem.
                </p>
                <div style={{ marginTop: "1.75rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "1.75rem 1.5rem 1.25rem" }}>
                  <HeadToHead />
                </div>
                <p className="byline" style={{ marginTop: "1rem", lineHeight: 1.7, maxWidth: "60ch" }}>
                  Stratified 40-problem slice · one-shot vs. best-of-16 · kernel-verified, n=40 (a few
                  points is noise). We excluded gpt-5 (its API key was revoked mid-run) and glm-5.2
                  (its proofs ran past a 48k-token budget — truncated, not a fair miss). We publish the
                  exclusions because catching the artifact is the point.
                </p>
              </Reveal>
            </Section>

            {/* ---------------- HONEST CEILING ---------------- */}
            <Section eyebrow="The honest ceiling" title="What it can't do yet.">
              <Reveal fade>
                <ul className="prose" style={{ marginTop: "1.75rem", maxWidth: "58ch" }}>
                  <li><strong>Olympiad math is mostly out of reach.</strong> 3 of 19 IMO problems — all classical. The rest stay unsolved no matter how much we sample.</li>
                  <li><strong>Below specialized provers.</strong> Purpose-built provers hit ~85&ndash;90%. We wrap a general model and reach 47%.</li>
                  <li><strong>A stronger model would score higher.</strong> One reached 53% on a slice, but couldn&rsquo;t run at full scale here. That&rsquo;s an infrastructure limit — named, not hidden.</li>
                </ul>
              </Reveal>
            </Section>

            <Reveal fade>
              <p className="byline" style={{ lineHeight: 1.7 }}>
                Reproducible: official miniF2F-test · gpt-oss-120b open weights · Lean 4 kernel v4.31.0.
                {" "}
                <a href="/data/pnrd1-minif2f-results.json">View the raw per-problem data →</a>
              </p>
            </Reveal>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
