/* Charts.tsx — hand-rolled inline SVG, no chart library.
   ALL numbers are the real, kernel-verified results from the 244-problem
   miniF2F-test run (gpt-oss-120b, best-of-16 + repair + few-shot).
   Bars carry .bar-grow / .bar-grow-x and animate when an ancestor <Reveal>
   sets data-revealed="true". Colors come from the frozen design tokens:
   green = the verified harness result, grey = the un-helped one-shot baseline. */

const ACCENT = "var(--accent)";
const ACCENT_BORDER = "var(--accent-border)";
const GREY = "var(--border-strong)";
const RAIL = "var(--surface-sunken)";
const GRID = "var(--border)";
const INK = "var(--text)";
const MUTED = "var(--muted)";
const FAINT = "var(--faint)";

const mono = (size: number, fill = INK, weight = 400) => ({
  fontFamily: "var(--font-mono)",
  fontSize: size,
  fontWeight: weight,
  fill,
  fontVariantNumeric: "tabular-nums" as const,
});
const sans = (size: number, fill = INK, weight = 400) => ({
  fontFamily: "var(--font-body)",
  fontSize: size,
  fontWeight: weight,
  fill,
});

/* ----------------------------- headline stat ----------------------------- */
export function HeadlineStat() {
  return (
    <div
      role="img"
      aria-label="One-shot 24.6 percent, 60 of 244, rising to PNRD#1 47.1 percent, 115 of 244 — every proof kernel-verified."
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.5ch", flexWrap: "wrap", lineHeight: 1 }}>
        <span style={{ fontFamily: "var(--font-display)", fontSize: "clamp(2.4rem,1.6rem+3vw,3.6rem)", color: MUTED, letterSpacing: "-0.02em" }}>
          24.6%
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "clamp(1.6rem,1rem+2vw,2.4rem)", color: FAINT, padding: "0 0.2ch" }}>→</span>
        <span style={{ fontFamily: "var(--font-display)", fontSize: "clamp(2.4rem,1.6rem+3vw,3.6rem)", color: "var(--accent-text)", letterSpacing: "-0.02em" }}>
          47.1%
        </span>
      </div>
      <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
        <span className="receipt">kernel-verified · 115 / 244</span>
        <span className="byline">≈ 1.9× · +22.5 pts · best-of-16 + repair + few-shot</span>
      </div>
    </div>
  );
}

/* --------------------------- lift bar chart ------------------------------ */
export function LiftChart() {
  const W = 480, H = 300;
  const padL = 52, padR = 20, padT = 38, baseline = 246;
  const plotH = baseline - padT; // 0..50%
  const perPct = plotH / 50;
  const y = (v: number) => baseline - v * perPct;
  const grids = [0, 10, 20, 30, 40, 50];
  const bars = [
    { label: "One-shot", value: 24.6, fill: GREY, stroke: "#BDBEB4" },
    { label: "PNRD#1 harness", value: 47.1, fill: ACCENT, stroke: ACCENT_BORDER },
  ];
  const slotW = (W - padL - padR) / bars.length;
  const barW = 96;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" focusable="false"
      aria-label="Bar chart: one-shot 24.6 percent versus PNRD#1 harness 47.1 percent on miniF2F-test, same open model.">
      <title>Test-time compute against a sound oracle</title>
      <desc>One-shot 24.6% (60/244) versus the PNRD#1 harness 47.1% (115/244).</desc>
      {grids.map((g) => (
        <g key={g} aria-hidden>
          <line x1={padL} x2={W - padR} y1={y(g)} y2={y(g)} stroke={GRID} strokeWidth={1} />
          <text x={padL - 10} y={y(g) + 4} textAnchor="end" style={mono(11, FAINT)}>{g}%</text>
        </g>
      ))}
      {bars.map((b, i) => {
        const cx = padL + slotW * i + slotW / 2;
        const x = cx - barW / 2;
        const top = y(b.value);
        return (
          <g key={b.label}>
            <rect x={x} y={padT} width={barW} height={baseline - padT} fill={RAIL} />
            <rect className="bar-grow" x={x} y={top} width={barW} height={baseline - top}
              fill={b.fill} stroke={b.stroke} strokeWidth={1} rx={3} style={{ transitionDelay: `${i * 90}ms` }} />
            <text x={cx} y={top - 10} textAnchor="middle" style={mono(15, i === 1 ? "var(--accent-text)" : INK, 500)}>
              {b.value}%
            </text>
            <text x={cx} y={baseline + 22} textAnchor="middle" style={sans(13, MUTED, 500)}>{b.label}</text>
            <text x={cx} y={baseline + 38} textAnchor="middle" style={mono(11, FAINT)}>
              {i === 0 ? "60 / 244" : "115 / 244"}
            </text>
          </g>
        );
      })}
      <text x={W - padR} y={padT - 14} textAnchor="end" style={mono(12, "var(--accent-text)", 500)}>
        ↑ 1.9× · +22.5 pts
      </text>
    </svg>
  );
}

/* --------------------------- family bar chart ---------------------------- */
type Fam = { name: string; total: number; oneshot: number; harness: number };
const FAMILIES: Fam[] = [
  { name: "mathd", total: 130, oneshot: 52, harness: 85 },
  { name: "amc", total: 45, oneshot: 2, harness: 13 },
  { name: "imo", total: 19, oneshot: 0, harness: 3 },
  { name: "aime", total: 15, oneshot: 3, harness: 4 },
  { name: "other", total: 35, oneshot: 3, harness: 10 },
];
// shared scale across families for honest cross-comparison
const FMAX = 130;

export function FamilyChart() {
  const W = 680;
  const rowH = 62;
  const padT = 14;
  const H = padT + FAMILIES.length * rowH + 10;
  const labelW = 150;
  const barX = labelW + 14;
  const barMax = W - barX - 70; // room for count labels
  const per = barMax / FMAX;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" focusable="false"
      aria-label="Grouped bar chart of kernel-verified solves by problem family. mathd 52 to 85, amc 2 to 13, imo 0 to 3, aime 3 to 4, other 3 to 10. Bars share one scale.">
      <title>Honest spread by problem family</title>
      {FAMILIES.map((f, i) => {
        const yTop = padT + i * rowH;
        const yc = yTop + rowH / 2;
        const owW = f.oneshot * per;
        const hW = f.harness * per;
        return (
          <g key={f.name}>
            <text x={8} y={yc - 8} style={sans(14, INK, 500)}>{f.name}</text>
            <text x={8} y={yc + 12} style={mono(11, FAINT)}>n={f.total}</text>

            {/* one-shot (grey) */}
            <rect x={barX} y={yc - 16} width={barMax} height={10} fill={RAIL} rx={2} aria-hidden />
            {f.oneshot > 0 ? (
              <rect className="bar-grow-x" x={barX} y={yc - 16} width={owW} height={10} fill={GREY} stroke="#BDBEB4" strokeWidth={0.75} rx={2} />
            ) : (
              <rect x={barX} y={yc - 16} width={2} height={10} fill={FAINT} aria-hidden />
            )}
            <text x={barX + Math.max(owW, 2) + 8} y={yc - 7} style={mono(11.5, MUTED)}>{f.oneshot}</text>

            {/* harness (green) */}
            <rect x={barX} y={yc + 0} width={barMax} height={10} fill={RAIL} rx={2} aria-hidden />
            <rect className="bar-grow-x" x={barX} y={yc + 0} width={hW} height={10} fill={ACCENT} stroke={ACCENT_BORDER} strokeWidth={0.75} rx={2} style={{ transitionDelay: "70ms" }} />
            <text x={barX + hW + 8} y={yc + 9} style={mono(12, "var(--accent-text)", 500)}>
              {f.harness}<tspan style={{ fill: FAINT, fontWeight: 400 }}>{` / ${f.total}`}</tspan>
            </text>
          </g>
        );
      })}
      {/* legend */}
      <g transform={`translate(${barX}, ${H - 2})`} aria-hidden>
        <rect x={0} y={-9} width={11} height={8} fill={GREY} rx={1.5} />
        <text x={16} y={-2} style={mono(11, MUTED)}>one-shot</text>
        <rect x={92} y={-9} width={11} height={8} fill={ACCENT} rx={1.5} />
        <text x={108} y={-2} style={mono(11, "var(--accent-text)")}>PNRD#1 harness</text>
      </g>
    </svg>
  );
}

/* ---------- verified head-to-head: accuracy + cost across models ---------- */
type H2HRow = { name: string; tag: string; acc: number; cpp: number; ours?: boolean };
const H2H: H2HRow[] = [
  { name: "gpt-oss-120b + PNRD#1", tag: "best-of-16 harness", acc: 42.5, cpp: 0.103, ours: true },
  { name: "kimi-k2.6", tag: "one-shot", acc: 32.5, cpp: 0.061 },
  { name: "deepseek-v4-pro", tag: "one-shot", acc: 30.0, cpp: 0.032 },
  { name: "gpt-oss-120b", tag: "one-shot", acc: 22.5, cpp: 0.004, ours: true },
];
const H2HMAX = 50;

export function HeadToHead() {
  const W = 680, rowH = 56, padT = 10;
  const H = padT + H2H.length * rowH + 4;
  const labelW = 196, barX = labelW + 12, barMax = W - barX - 124;
  const per = barMax / H2HMAX;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" focusable="false"
      aria-label="Verified accuracy on the same 40 miniF2F problems, kernel-checked: gpt-oss-120b plus PNRD#1 harness 42.5 percent at 10 cents per problem, kimi-k2.6 one-shot 32.5 at 6 cents, deepseek-v4-pro one-shot 30 at 3 cents, gpt-oss-120b one-shot 22.5 at 0.4 cents.">
      <title>Verified head-to-head — accuracy and cost</title>
      {H2H.map((r, i) => {
        const yc = padT + i * rowH + rowH / 2;
        const w = r.acc * per;
        return (
          <g key={r.name}>
            <text x={8} y={yc - 5} style={sans(14, INK, r.ours ? 600 : 500)}>{r.name}</text>
            <text x={8} y={yc + 13} style={mono(10.5, FAINT)}>{r.tag}</text>
            <rect x={barX} y={yc - 11} width={barMax} height={18} fill={RAIL} rx={3} aria-hidden />
            <rect className="bar-grow-x" x={barX} y={yc - 11} width={w} height={18}
              fill={r.ours ? ACCENT : GREY} stroke={r.ours ? ACCENT_BORDER : "#BDBEB4"} strokeWidth={0.75} rx={3}
              style={{ transitionDelay: `${i * 60}ms` }} />
            <text x={barX + w + 8} y={yc + 3} style={mono(13, r.ours ? "var(--accent-text)" : INK, 600)}>
              {r.acc}%<tspan style={{ fill: FAINT, fontWeight: 400 }}>{`  ·  $${r.cpp < 0.01 ? r.cpp.toFixed(3) : r.cpp.toFixed(2)}/prob`}</tspan>
            </text>
          </g>
        );
      })}
    </svg>
  );
}
