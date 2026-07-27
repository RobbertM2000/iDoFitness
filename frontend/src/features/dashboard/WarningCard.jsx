import { useState } from "react";

const SEVERITY_COLOR = { high: "var(--danger)", medium: "var(--warning)", low: "var(--text-muted)" };

export default function WarningCard({ warning, onDismiss }) {
  const [dismissing, setDismissing] = useState(false);
  const color = SEVERITY_COLOR[warning.severity] || "var(--text-muted)";

  const handleDismiss = async () => {
    setDismissing(true);
    try {
      await onDismiss(warning.id);
    } catch {
      setDismissing(false);
    }
  };

  return (
    <div
      style={{
        display: "flex", gap: 10, alignItems: "flex-start",
        background: "var(--surface)", borderRadius: 12, padding: 14,
        borderLeft: `3px solid ${color}`, marginBottom: 8,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 20, height: 20, borderRadius: "50%", background: color, color: "#fff",
          fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, marginTop: 1,
        }}
      >
        !
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>{warning.message}</p>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-muted)" }}>{warning.action_hint}</p>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        disabled={dismissing}
        aria-label="Waarschuwing sluiten"
        style={{
          background: "none", border: "none", color: "var(--text-muted)",
          cursor: dismissing ? "default" : "pointer", fontSize: 18, lineHeight: 1, padding: 2,
          flexShrink: 0, opacity: dismissing ? 0.5 : 1,
        }}
      >
        ×
      </button>
    </div>
  );
}
