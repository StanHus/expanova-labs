import Link from "next/link";
import Reveal from "@/components/Reveal";

export default function Home() {
  return (
    <div className="theme-dark" style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "1.5rem 1.75rem" }}>
        <span className="ill-label" aria-hidden>EST. 2026</span>
      </div>

      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "2rem 1.5rem 4rem",
        }}
      >
        <Reveal fade>
          <svg width="56" height="50" viewBox="0 0 56 50" aria-hidden style={{ marginBottom: "1.75rem" }}>
            <path d="M28 4 L52 46 L4 46 Z" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinejoin="round" />
          </svg>

          <h1 className="logotype" style={{ fontSize: "clamp(2.1rem, 1.3rem + 4.4vw, 4.25rem)" }}>
            Expanova
            <br />
            Labs
          </h1>

          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.9375rem",
              lineHeight: 1.7,
              color: "var(--muted)",
              maxWidth: "40ch",
              margin: "1.9rem auto 0",
            }}
          >
            Verification-first AI. We build systems that prove their work — checked by an objective
            oracle, not claimed by a model.
          </p>

          <nav
            style={{
              marginTop: "2.4rem",
              display: "flex",
              gap: "1.1rem",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-mono)",
              fontSize: "0.9375rem",
            }}
          >
            <Link href="/pnrd-1" style={{ color: "var(--accent-text)", textDecorationColor: "var(--accent-border)" }}>PNRD#1</Link>
            <span aria-hidden style={{ color: "var(--faint)" }}>·</span>
            <Link href="/approach" style={{ color: "var(--accent-text)", textDecorationColor: "var(--accent-border)" }}>Approach</Link>
          </nav>

          <p className="ill-label" style={{ marginTop: "2.6rem", color: "var(--faint)" }}>
            ✓ blocked beats faked
          </p>
        </Reveal>
      </main>
    </div>
  );
}
