const RPE_OPTIONS = [6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10];

function rpeTargetLabel(suggestion) {
  if (!suggestion || suggestion.rpe_target_min == null) return null;
  const { rpe_target_min, rpe_target_max } = suggestion;
  return rpe_target_min === rpe_target_max
    ? `RPE ${rpe_target_min}`
    : `RPE ${rpe_target_min}-${rpe_target_max}`;
}

function rpeHitResult(set, suggestion) {
  if (!suggestion || set.rpe === "" || suggestion.rpe_target_min == null) return null;
  const rpe = Number(set.rpe);
  const { rpe_target_min, rpe_target_max } = suggestion;
  if (rpe >= rpe_target_min && rpe <= rpe_target_max) {
    return { text: "✓ RPE-doel gehaald", color: "var(--success)" };
  }
  return rpe < rpe_target_min
    ? { text: "Onder RPE-doel", color: "var(--text-muted)" }
    : { text: "Boven RPE-doel", color: "var(--warning)" };
}

export default function SetRow({ set, index, onChange, onComplete, onRemove }) {
  const done = set.completed;
  const suggestion = set.suggestion;
  const hit = done ? rpeHitResult(set, suggestion) : null;

  return (
    <div
      style={{
        padding: "8px 4px",
        background: done ? "rgba(22,163,74,0.08)" : "transparent",
        borderRadius: 8, marginBottom: 4,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 18, fontSize: 13, color: "var(--text-muted)", textAlign: "center" }}>
          {index + 1}
        </span>

        <input
          type="number"
          inputMode="decimal"
          placeholder={suggestion?.weight_kg != null ? String(suggestion.weight_kg) : "kg"}
          value={set.weight_kg}
          disabled={done}
          onChange={(e) => onChange({ weight_kg: e.target.value })}
          style={cellInputStyle}
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder={suggestion?.reps != null ? String(suggestion.reps) : "reps"}
          value={set.reps}
          disabled={done}
          onChange={(e) => onChange({ reps: e.target.value })}
          style={{ ...cellInputStyle, width: 56 }}
        />

        <select
          value={set.rpe}
          disabled={done}
          onChange={(e) => onChange({ rpe: e.target.value })}
          style={{ ...cellInputStyle, width: 64 }}
        >
          <option value="">{rpeTargetLabel(suggestion) || "RPE"}</option>
          {RPE_OPTIONS.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>

        <button
          type="button"
          onClick={onComplete}
          disabled={done}
          aria-label="Set klaar"
          style={{
            width: 36, height: 36, borderRadius: 8, flexShrink: 0,
            border: `1px solid ${done ? "var(--success)" : "var(--text-muted)"}`,
            background: done ? "var(--success)" : "var(--surface)",
            color: done ? "#fff" : "var(--text)", cursor: done ? "default" : "pointer",
            fontSize: 16,
          }}
        >
          ✓
        </button>

        {!done && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Set verwijderen"
            style={{
              width: 28, height: 28, borderRadius: 8, flexShrink: 0, border: "none",
              background: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 16,
            }}
          >
            ×
          </button>
        )}
      </div>

      {hit && (
        <div style={{ fontSize: 11, color: hit.color, marginLeft: 26, marginTop: 2 }}>
          {hit.text}
        </div>
      )}
    </div>
  );
}

const cellInputStyle = {
  width: 64, height: 36, padding: "0 8px", borderRadius: 8,
  border: "1px solid var(--text-muted)", background: "var(--surface)",
  color: "var(--text)", fontSize: 15,
};
