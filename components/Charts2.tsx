/* Charts2.tsx — PNRD#2 charts. Hand-rolled inline SVG, no chart library, server-safe.
   Every number is passed in from result JSON read at build time; nothing is typed by hand.
   Colors come from the frozen design tokens: green = verified harness result,
   grey = the un-helped one-shot, amber = where the law is being tested / not yet run. */

const ACCENT = "var(--accent)";
const ACCENT_BORDER = "var(--accent-border)";
const GREY = "var(--border-strong)";
const GRID = "var(--border)";
const INK = "var(--text)";
const MUTED = "var(--muted)";
const FAINT = "var(--faint)";
const KILL = "var(--kill)";

const mono = (size: number, fill = INK, weight = 400) => ({
  fontFamily: "var(--font-mono)", fontSize: size, fontWeight: weight, fill,
  fontVariantNumeric: "tabular-nums" as const,
});
const sans = (size: number, fill = INK, weight = 400) => ({
  fontFamily: "var(--font-body)", fontSize: size, fontWeight: weight, fill,
});

export type OracleRow = {
  label: string;        // "PNRD#1 · Lean 4 kernel · miniF2F"
  model: string;        // "gpt-oss-120b"
  n: number;
  oneShot: number;      // count
  harness: number;      // count
  pending?: boolean;    // registered arm that has not run
};

/* ------------------------- the law, tested per oracle ------------------------- */
export function OracleLift({ rows }: { rows: OracleRow[] }) {
  const W = 640, rowH = 78, padL = 16, padR = 16, top = 12;
  const H = top + rows.length * rowH + 8;
  const barW = W - padL - padR;
  const x = (pct: number) => padL + (barW * pct) / 100;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" focusable="false"
      aria-label={rows.map((r) => `${r.label}: one-shot ${((100 * r.oneShot) / r.n).toFixed(1)} percent, harness ${((100 * r.harness) / r.n).toFixed(1)} percent, n ${r.n}`).join(". ")}>
      {[0, 25, 50, 75, 100].map((g) => (
        <g key={g}>
          <line x1={x(g)} y1={top} x2={x(g)} y2={H - 8} stroke={GRID} strokeDasharray="2 4" />
          <text x={x(g)} y={H - 0} textAnchor="middle" style={mono(10, FAINT)}>{g}%</text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y0 = top + i * rowH;
        const a = (100 * r.oneShot) / r.n, b = (100 * r.harness) / r.n;
        return (
          <g key={r.label}>
            <text x={padL} y={y0 + 12} style={sans(12.5, INK, 600)}>{r.label}</text>
            <text x={W - padR} y={y0 + 12} textAnchor="end" style={mono(10.5, MUTED)}>{r.model} · n={r.n}</text>
            {r.pending ? (
              <>
                <rect x={padL} y={y0 + 22} width={barW} height={30} rx={3} fill="none" stroke={GRID} strokeDasharray="4 4" />
                <text x={padL + 10} y={y0 + 41} style={mono(11, MUTED)}>registered · not yet run · gate fixed in PREREG.md</text>
              </>
            ) : (
              <>
                <rect x={padL} y={y0 + 22} width={x(a) - padL} height={13} rx={2} fill={GREY} />
                <text x={x(a) + 6} y={y0 + 33} style={mono(11, MUTED)}>{a.toFixed(1)}% one-shot</text>
                <rect className="bar-grow-x" x={padL} y={y0 + 39} width={x(b) - padL} height={13} rx={2} fill={ACCENT} stroke={ACCENT_BORDER} />
                <text x={x(b) + 6} y={y0 + 50} style={mono(11, "var(--accent-text)", 700)}>{b.toFixed(1)}% verified · +{(b - a).toFixed(1)} pts</text>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/* --------------------------- pass@k saturation curve --------------------------- */
export function PassAtK({ series, n, maxK }: {
  series: { label: string; counts: number[]; primary?: boolean }[]; // counts[k-1] = cumulative solves by attempt k
  n: number; maxK: number;
}) {
  const W = 640, H = 300, padL = 52, padR = 20, padT = 24, padB = 40;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxPct = Math.max(50, ...series.flatMap((s) => s.counts.map((c) => (100 * c) / (s.primary ? n : n))));
  const top = Math.ceil(maxPct / 10) * 10;
  const x = (k: number) => padL + ((k - 1) / (maxK - 1)) * plotW;
  const y = (pct: number) => padT + plotH - (pct / top) * plotH;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" focusable="false"
      aria-label={series.map((s) => `${s.label}: ${s.counts.map((c, i) => `${i + 1}:${c}`).join(", ")}`).join(". ")}>
      {Array.from({ length: top / 10 + 1 }, (_, i) => i * 10).map((g) => (
        <g key={g}>
          <line x1={padL} y1={y(g)} x2={W - padR} y2={y(g)} stroke={GRID} />
          <text x={padL - 8} y={y(g) + 4} textAnchor="end" style={mono(10.5, FAINT)}>{g}%</text>
        </g>
      ))}
      {[1, 2, 4, 8, 12, 16].filter((k) => k <= maxK).map((k) => (
        <text key={k} x={x(k)} y={H - 14} textAnchor="middle" style={mono(10.5, FAINT)}>k={k}</text>
      ))}
      <line x1={x(8)} y1={padT} x2={x(8)} y2={padT + plotH} stroke={GRID} strokeDasharray="3 4" />
      <text x={x(8) + 4} y={padT + 10} style={mono(10, FAINT)}>attempt 8</text>
      {series.map((s) => {
        const pts = s.counts.map((c, i) => `${x(i + 1)},${y((100 * c) / n)}`).join(" ");
        const last = s.counts[s.counts.length - 1];
        return (
          <g key={s.label}>
            <polyline points={pts} fill="none" stroke={s.primary ? ACCENT : GREY} strokeWidth={s.primary ? 2.5 : 1.75} strokeLinejoin="round" />
            {s.counts.map((c, i) => (
              <circle key={i} cx={x(i + 1)} cy={y((100 * c) / n)} r={s.primary ? 3 : 2.2} fill={s.primary ? ACCENT : GREY} />
            ))}
            <text x={x(s.counts.length) - 4} y={y((100 * last) / n) - 8} textAnchor="end" style={mono(11, s.primary ? "var(--accent-text)" : MUTED, 600)}>
              {s.label} · {((100 * last) / n).toFixed(1)}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ----------------------- where the verifier checks went ----------------------- */
export function BudgetSplit({ rows }: { rows: { label: string; total: number; onUnsolved: number }[] }) {
  const W = 640, rowH = 56, padL = 16, padR = 16;
  const H = rows.length * rowH + 4;
  const barW = W - padL - padR;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" focusable="false"
      aria-label={rows.map((r) => `${r.label}: ${r.total} verifier checks, ${((100 * r.onUnsolved) / r.total).toFixed(0)} percent on programs never solved`).join(". ")}>
      {rows.map((r, i) => {
        const y0 = i * rowH;
        const wasted = (100 * r.onUnsolved) / r.total;
        return (
          <g key={r.label}>
            <text x={padL} y={y0 + 12} style={sans(12.5, INK, 600)}>{r.label}</text>
            <text x={W - padR} y={y0 + 12} textAnchor="end" style={mono(10.5, MUTED)}>{r.total.toLocaleString()} checks</text>
            <rect x={padL} y={y0 + 20} width={barW} height={16} rx={3} fill={ACCENT} opacity={0.35} />
            <rect className="bar-grow-x" x={padL} y={y0 + 20} width={(barW * wasted) / 100} height={16} rx={3} fill={KILL} opacity={0.75} />
            <text x={padL + 8} y={y0 + 32} style={mono(10.5, "#fff", 700)}>{wasted.toFixed(0)}% spent on programs that never solved</text>
          </g>
        );
      })}
    </svg>
  );
}
