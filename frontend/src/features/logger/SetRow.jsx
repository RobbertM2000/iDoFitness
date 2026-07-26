const RPE_MIN = 1;
const RPE_MAX = 10;
const RPE_STEP = 0.5;

function clampRpe(v) {
  return Math.min(RPE_MAX, Math.max(RPE_MIN, v));
}

function stepRpe(current, suggestion, delta) {
  const base = current != null && !Number.isNaN(current) ? current : suggestion?.rpe ?? 7;
  return clampRpe(Math.round((base + delta) / RPE_STEP) * RPE_STEP);
}

function rpeHitResult(rpeValue, suggestion) {
  if (!suggestion || rpeValue === "" || suggestion.rpe_target_min == null) return null;
  const rpe = Number(rpeValue);
  const { rpe_target_min, rpe_target_max } = suggestion;
  if (rpe >= rpe_target_min && rpe <= rpe_target_max) {
    return { text: "✓ Doel gehaald!", color: "var(--success)", hit: true };
  }
  return rpe < rpe_target_min
    ? { text: "Onder RPE-doel", color: "var(--text-muted)", hit: false }
    : { text: "Boven RPE-doel", color: "var(--warning)", hit: false };
}

function RpeControl({ set, suggestion, done, onChange }) {
  const hasValue = set.rpe !== "";
  const numeric = hasValue ? Number(set.rpe) : null;
  const live = rpeHitResult(set.rpe, suggestion);

  const adjust = (delta) => {
    if (done) return;
    onChange({ rpe: String(stepRpe(numeric, suggestion, delta)) });
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
      <div
        style={{
          display: "flex", alignItems: "center", flexShrink: 0,
          border: "1px solid var(--text-muted)", borderRadius: 8,
          height: 36, overflow: "hidden",
        }}
      >
        <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", padding: "0 2px 0 4px" }}>
          RPE
        </span>
        <button
          type="button"
          onClick={() => adjust(-RPE_STEP)}
          disabled={done}
          aria-label="RPE omlaag"
          style={rpeStepButtonStyle}
        >
          −
        </button>
        <input
          className="rpe-input"
          type="number"
          inputMode="decimal"
          step={RPE_STEP}
          min={RPE_MIN}
          max={RPE_MAX}
          placeholder={suggestion?.rpe != null ? String(suggestion.rpe) : "–"}
          value={set.rpe}
          disabled={done}
          onChange={(e) => onChange({ rpe: e.target.value })}
          style={{
            width: 24, height: "100%", border: "none", background: "transparent",
            textAlign: "center", fontSize: 13, fontWeight: 600, padding: 0,
            color: done ? "var(--text)" : hasValue ? "var(--primary)" : "var(--text-muted)",
          }}
        />
        <button
          type="button"
          onClick={() => adjust(RPE_STEP)}
          disabled={done}
          aria-label="RPE omhoog"
          style={rpeStepButtonStyle}
        >
          +
        </button>
      </div>

      {live?.hit && (
        <span title="RPE-doel gehaald" style={{ color: "var(--success)", fontSize: 14, flexShrink: 0 }}>
          ✓
        </span>
      )}
    </div>
  );
}

const rpeStepButtonStyle = {
  width: 16, height: "100%", flexShrink: 0, border: "none", padding: 0,
  background: "var(--surface)", color: "var(--text-muted)", fontSize: 14,
  cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
};

export default function SetRow({ set, index, onChange, onComplete, onRemove }) {
  const done = set.completed;
  const suggestion = set.suggestion;
  const hit = done ? rpeHitResult(set.rpe, suggestion) : null;

  return (
    <div
      style={{
        padding: "8px 4px",
        background: done ? "rgba(22,163,74,0.08)" : "transparent",
        borderRadius: 8, marginBottom: 4,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", rowGap: 6 }}>
        <span style={{ width: 16, fontSize: 13, color: "var(--text-muted)", textAlign: "center", flexShrink: 0 }}>
          {index + 1}
        </span>

        <input
          type="number"
          inputMode="decimal"
          placeholder={suggestion?.weight_kg != null ? String(suggestion.weight_kg) : "kg"}
          value={set.weight_kg}
          disabled={done}
          onChange={(e) => onChange({ weight_kg: e.target.value })}
          style={{ ...cellInputStyle, width: 52 }}
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder={suggestion?.reps != null ? String(suggestion.reps) : "reps"}
          value={set.reps}
          disabled={done}
          onChange={(e) => onChange({ reps: e.target.value })}
          style={{ ...cellInputStyle, width: 58, padding: "0 6px" }}
        />

        <RpeControl set={set} suggestion={suggestion} done={done} onChange={onChange} />

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
        <div style={{ fontSize: 11, color: hit.color, marginLeft: 22, marginTop: 2 }}>
          {hit.text}
        </div>
      )}
    </div>
  );
}

const cellInputStyle = {
  height: 36, padding: "0 8px", borderRadius: 8,
  border: "1px solid var(--text-muted)", background: "var(--surface)",
  color: "var(--text)", fontSize: 15,
};
