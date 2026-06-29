export default function Wordmark({ size = "0.8125rem" }: { size?: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.7ch",
        fontFamily: "var(--font-mono)",
        fontSize: size,
        fontWeight: 500,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
        color: "var(--text)",
      }}
    >
      <span className="tri-mark" aria-hidden />
      EXPANOVA&nbsp;LABS
    </span>
  );
}
