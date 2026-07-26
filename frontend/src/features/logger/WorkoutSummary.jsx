import { formatMMSS } from "../../hooks/useTimer";

const PR_LABELS = {
  weight: "Gewicht", reps: "Reps", e1rm: "e1RM", tonnage: "Tonnage",
};

export default function WorkoutSummary({ result, onDone }) {
  const { workout, summary } = result;

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: 24, textAlign: "center" }}>
      <div style={{ fontSize: 40 }}>🎉</div>
      <h2 style={{ fontSize: 22, fontWeight: 600, margin: "8px 0" }}>Workout voltooid</h2>
      <p style={{ color: "var(--text-muted)" }}>{workout.title || "Workout"}</p>

      <div style={{ display: "flex", justifyContent: "center", gap: 24, margin: "24px 0" }}>
        <Stat label="Duur" value={workout.duration_sec ? formatMMSS(workout.duration_sec) : "—"} />
        <Stat label="Sets" value={summary.total_sets} />
        <Stat label="Tonnage" value={`${summary.total_tonnage} kg`} />
      </div>

      {summary.new_prs.length > 0 && (
        <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, textAlign: "left", marginBottom: 16 }}>
          <p style={{ fontWeight: 600, marginBottom: 8 }}>🏆 Nieuwe records</p>
          {summary.new_prs.map((pr, i) => (
            <p key={i} style={{ margin: "4px 0", fontSize: 14 }}>
              {pr.exercise} — {PR_LABELS[pr.type] || pr.type}: <strong>{pr.value}</strong>
              {pr.type === "weight" ? " kg" : pr.type === "e1rm" ? " kg" : pr.type === "tonnage" ? " kg" : ""}
            </p>
          ))}
        </div>
      )}

      <button
        onClick={onDone}
        style={{
          width: "100%", height: 48, borderRadius: 10, border: "none",
          background: "var(--primary)", color: "#fff", fontSize: 16, fontWeight: 600, cursor: "pointer",
        }}
      >
        Klaar
      </button>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</div>
    </div>
  );
}
