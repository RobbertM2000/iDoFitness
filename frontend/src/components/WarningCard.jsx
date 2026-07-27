import { useState } from "react";

const SEVERITY_COLOR = { high: "var(--danger)", medium: "var(--warning)", low: "var(--text-muted)" };

// White Paper §8.5 — only deload_needed has a concrete next action today.
// Other warning types (plateau, muscle_imbalance, ...) are informational;
// add an entry here if/when a dedicated flow exists for them.
const ACTION_LABEL = {
  deload_needed: "Plan deload-week",
};

export default function WarningCard({ warning, onDismiss, onAction }) {
  const [dismissing, setDismissing] = useState(false);
  const color = SEVERITY_COLOR[warning.severity] || "var(--text-muted)";
  const actionLabel = ACTION_LABEL[warning.warning_type];

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
        {actionLabel && onAction && (
          <button
            type="button"
            onClick={() => onAction(warning.warning_type)}
            style={{
              background: "none", border: "none", color: "var(--primary)",
              cursor: "pointer", fontSize: 13, fontWeight: 600, padding: "6px 0 0",
            }}
          >
            {actionLabel} →
          </button>
        )}
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
