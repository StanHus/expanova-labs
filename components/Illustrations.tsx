/* Illustrations.tsx — crisp, high-level inline-SVG diagrams.
   Colors come from CSS tokens (var()), so they adapt to light/dark. */

const mono = (size: number, fill = "var(--text)", weight = 400) => ({
  fontFamily: "var(--font-mono)",
  fontSize: size,
  fontWeight: weight,
  fill,
});

/* ---------- 1. How PNRD#1 works: sample → check → repair → verified ---------- */
export function HarnessFlow() {
  const SURF = "var(--surface)";
  const BORD = "var(--border-strong)";
  const ACC = "var(--accent)";
  const FAINT = "var(--faint)";
  const box = (x: number, w: number, accent = false) => ({
    x, y: 56, width: w, height: 72, rx: 8,
    fill: SURF, stroke: accent ? ACC : BORD, strokeWidth: accent ? 1.5 : 1,
  });
  return (
    <svg viewBox="0 0 780 250" width="100%" role="img" focusable="false"
      aria-label="How PNRD#1 works: the open model writes N candidate proofs; the Lean 4 kernel checks each; failures are repaired with the kernel's exact error and resampled; a proof that compiles becomes a verified proof, otherwise nothing.">
      <title>How PNRD#1 works</title>
      <defs>
        <marker id="ah" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto">
          <path d="M0,0 L6.5,3 L0,6 Z" fill={FAINT} />
        </marker>
        <marker id="ahg" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto">
          <path d="M0,0 L6.5,3 L0,6 Z" fill={ACC} />
        </marker>
      </defs>

      {/* node 1: model */}
      <rect {...box(8, 124)} />
      <text x={70} y={88} textAnchor="middle" style={mono(13, "var(--text)", 500)}>Open model</text>
      <text x={70} y={106} textAnchor="middle" style={mono(10.5, FAINT)}>gpt-oss-120b</text>

      {/* node 2: N proofs (stacked) */}
      <rect x={206} y={62} width={132} height={72} rx={8} fill={SURF} stroke={BORD} />
      <rect x={200} y={56} width={132} height={72} rx={8} fill={SURF} stroke={BORD} />
      <text x={266} y={88} textAnchor="middle" style={mono(13, "var(--text)", 500)}>N candidate</text>
      <text x={266} y={106} textAnchor="middle" style={mono(13, "var(--text)", 500)}>proofs</text>

      {/* node 3: kernel gate */}
      <rect {...box(404, 128, true)} />
      <text x={468} y={86} textAnchor="middle" style={mono(13, ACC, 700)}>Lean 4 kernel</text>
      <text x={468} y={104} textAnchor="middle" style={mono(10, FAINT)}>mechanical, not an LLM</text>

      {/* node 4: verified */}
      <rect x={620} y={56} width={152} height={72} rx={8} fill="var(--verified-bg)" stroke="var(--accent-border)" strokeWidth={1.5} />
      <text x={696} y={88} textAnchor="middle" style={mono(13, "var(--accent-text)", 700)}>✓ Verified</text>
      <text x={696} y={106} textAnchor="middle" style={mono(11, "var(--accent-text)")}>or nothing</text>

      {/* arrows main row */}
      <line x1={132} y1={92} x2={196} y2={92} stroke={FAINT} strokeWidth={1.4} markerEnd="url(#ah)" />
      <text x={164} y={82} textAnchor="middle" style={mono(9.5, FAINT)}>writes N</text>
      <line x1={338} y1={92} x2={400} y2={92} stroke={FAINT} strokeWidth={1.4} markerEnd="url(#ah)" />
      <text x={369} y={82} textAnchor="middle" style={mono(9.5, FAINT)}>checks each</text>
      <line x1={532} y1={92} x2={616} y2={92} stroke={ACC} strokeWidth={1.6} markerEnd="url(#ahg)" />
      <text x={574} y={82} textAnchor="middle" style={mono(9.5, "var(--accent-text)")}>compiles ✓</text>

      {/* repair loop */}
      <path d="M 468 132 V 188 Q 468 204 452 204 H 86 Q 70 204 70 188 V 134"
        fill="none" stroke={FAINT} strokeWidth={1.4} strokeDasharray="4 3" markerEnd="url(#ah)" />
      <text x={269} y={224} textAnchor="middle" style={mono(10.5, "var(--muted)")}>
        ✗ fails → repair: the kernel&rsquo;s exact error goes back to the model
      </text>
    </svg>
  );
}

/* ---------- 2. A mechanical judge: no LLM to bluff ---------- */
export function OracleGate() {
  const ACC = "var(--accent)";
  const FAINT = "var(--faint)";
  const KILL = "var(--kill)";
  return (
    <svg viewBox="0 0 560 230" width="100%" role="img" focusable="false"
      aria-label="A mechanical judge. A proof passes only if the Lean kernel compiles it with no sorry, no admit, and no forbidden token — that path is green. Anything else is blocked. There is no LLM to talk into a yes.">
      <title>A mechanical judge — no model to bluff</title>
      <defs>
        <marker id="ag" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6 Z" fill={ACC} /></marker>
        <marker id="ak" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6 Z" fill={FAINT} /></marker>
      </defs>

      {/* the gate */}
      <rect x={250} y={40} width={60} height={150} rx={8} fill="var(--surface)" stroke={ACC} strokeWidth={1.5} />
      <text x={280} y={28} textAnchor="middle" style={mono(11, ACC, 700)}>KERNEL</text>
      <text x={280} y={118} textAnchor="middle" style={{ fontFamily: "var(--font-mono)", fontSize: 22, fill: ACC, fontWeight: 700 }}>⊢</text>

      {/* PASS path */}
      <line x1={70} y1={86} x2={244} y2={86} stroke={ACC} strokeWidth={1.6} markerEnd="url(#ag)" />
      <text x={70} y={74} style={mono(11, "var(--text)", 500)}>compiles · no sorry · no admit</text>
      <line x1={316} y1={86} x2={486} y2={86} stroke={ACC} strokeWidth={1.6} markerEnd="url(#ag)" />
      <rect x={486} y={72} width={64} height={28} rx={14} fill="var(--verified-bg)" stroke="var(--accent-border)" />
      <text x={518} y={90} textAnchor="middle" style={mono(12, "var(--accent-text)", 700)}>✓ PASS</text>

      {/* FAIL path */}
      <line x1={70} y1={150} x2={244} y2={150} stroke={FAINT} strokeWidth={1.4} strokeDasharray="4 3" markerEnd="url(#ak)" />
      <text x={70} y={138} style={mono(11, "var(--muted)")}>anything else</text>
      <line x1={250} y1={150} x2={316} y2={150} stroke={KILL} strokeWidth={1.4} />
      <text x={283} y={143} textAnchor="middle" style={mono(13, KILL, 700)}>✗</text>
      <text x={332} y={154} style={mono(11.5, "var(--muted)")}>blocked</text>

      <text x={280} y={216} textAnchor="middle" style={mono(11, FAINT)}>
        the check is mechanical — there is no model to talk into a yes
      </text>
    </svg>
  );
}
