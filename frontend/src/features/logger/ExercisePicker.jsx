import { useEffect, useState } from "react";
import { api } from "../../api/client";

const MUSCLES = [
  "chest", "back", "quads", "hamstrings", "glutes",
  "shoulders", "biceps", "triceps", "calves", "abs",
];

const MUSCLE_LABELS = {
  chest: "Borst", back: "Rug", quads: "Quads", hamstrings: "Hamstrings",
  glutes: "Glutes", shoulders: "Schouders", biceps: "Biceps",
  triceps: "Triceps", calves: "Kuiten", abs: "Buik",
};

export default function ExercisePicker({ onSelect, onClose }) {
  const [query, setQuery] = useState("");
  const [muscle, setMuscle] = useState(null);
  const [exercises, setExercises] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (muscle) params.set("muscle", muscle);
    const timeout = setTimeout(() => {
      api.get(`/exercises?${params.toString()}`)
        .then((data) => setExercises(data.exercises))
        .finally(() => setLoading(false));
    }, 200); // light debounce while typing
    return () => clearTimeout(timeout);
  }, [query, muscle]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "var(--bg)", zIndex: 100,
        display: "flex", flexDirection: "column", padding: 16,
      }}
    >
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          autoFocus
          placeholder="Zoek een oefening…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            flex: 1, height: 44, padding: "0 12px", borderRadius: 10,
            border: "1px solid var(--text-muted)", background: "var(--surface)",
            color: "var(--text)", fontSize: 16,
          }}
        />
        <button onClick={onClose} style={{ padding: "0 16px", borderRadius: 10, border: "none", background: "none", color: "var(--text-muted)", cursor: "pointer" }}>
          Sluiten
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8, marginBottom: 8 }}>
        <Chip active={!muscle} onClick={() => setMuscle(null)} label="Alles" />
        {MUSCLES.map((m) => (
          <Chip key={m} active={muscle === m} onClick={() => setMuscle(m)} label={MUSCLE_LABELS[m]} />
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading && <p style={{ color: "var(--text-muted)" }}>Zoeken…</p>}
        {!loading && exercises.length === 0 && (
          <p style={{ color: "var(--text-muted)" }}>Geen oefeningen gevonden.</p>
        )}
        {exercises.map((ex) => (
          <button
            key={ex.id}
            onClick={() => onSelect(ex)}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              width: "100%", textAlign: "left", padding: "12px 8px",
              borderBottom: "1px solid var(--text-muted)", background: "none",
              border: "none", borderBottomWidth: 1, borderBottomStyle: "solid",
              borderBottomColor: "var(--text-muted)", color: "var(--text)", cursor: "pointer",
            }}
          >
            <div>
              <div style={{ fontWeight: 500 }}>{ex.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {MUSCLE_LABELS[ex.muscle] || ex.muscle} · {ex.is_compound ? "Compound" : "Isolatie"}
              </div>
            </div>
            {ex.is_avoided && <span title="Op je vermijdlijst">⚠️</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

function Chip({ active, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        flexShrink: 0, padding: "6px 12px", borderRadius: 999,
        border: `1px solid ${active ? "var(--primary)" : "var(--text-muted)"}`,
        background: active ? "var(--primary)" : "transparent",
        color: active ? "#fff" : "var(--text)", fontSize: 13, cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}
