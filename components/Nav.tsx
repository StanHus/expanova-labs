import Link from "next/link";
import Wordmark from "./Wordmark";

const LINKS = [
  { label: "PNRD#1", href: "/pnrd-1" },
  { label: "PNRD#2", href: "/pnrd-2" },
  { label: "Approach", href: "/approach" },
];

export default function Nav() {
  return (
    <header
      className="sticky top-0 z-50 border-b border-border"
      style={{ background: "color-mix(in srgb, var(--bg) 88%, transparent)", backdropFilter: "blur(8px)" }}
    >
      <nav className="wide flex h-14 items-center justify-between">
        <Link href="/" aria-label="Par&Rec Labs — home" style={{ textDecoration: "none" }}>
          <Wordmark />
        </Link>
        <ul className="flex items-center gap-5 sm:gap-7 m-0 p-0" style={{ listStyle: "none" }}>
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="text-muted"
                style={{
                  fontSize: "0.9rem",
                  fontWeight: 500,
                  textDecoration: "none",
                }}
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
