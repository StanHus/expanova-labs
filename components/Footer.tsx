import Link from "next/link";
import Wordmark from "./Wordmark";

const LINKS = [
  { label: "PNRD#1", href: "/pnrd-1" },
  { label: "Method", href: "/pnrd-1#method" },
  { label: "Results", href: "/pnrd-1#results" },
  { label: "Raw data", href: "/data/pnrd1-minif2f-results.json" },
];

export default function Footer() {
  return (
    <footer className="footer mt-auto">
      <div className="kernel-strip py-2 text-center" aria-hidden>
        {"PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓  PASS ✓"}
      </div>
      <div className="wide py-12">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-sm">
            <Wordmark size="0.875rem" />
            <p className="dek mt-3" style={{ fontSize: "1rem" }}>
              Blocked beats faked.
            </p>
            <p className="byline mt-4">✓ Checked by Lean 4 kernel · v4.31.0</p>
          </div>
          <ul className="flex flex-col gap-3 m-0 p-0" style={{ listStyle: "none" }}>
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-text" style={{ textDecorationColor: "var(--border-strong)" }}>
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <hr className="hairline my-8" />
        <p className="byline">© 2026 Expanova Labs · Verification-first AI</p>
      </div>
    </footer>
  );
}
