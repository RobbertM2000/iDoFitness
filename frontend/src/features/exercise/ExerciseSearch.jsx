import { useEffect, useState } from "react";
import { api } from "../../api/client";

const MUSCLE_LABELS = {
  chest: "Borst", back: "Rug", quads: "Quads", hamstrings: "Hamstrings",
  glutes: "Glutes", shoulders: "Schouders", biceps: "Biceps",
  triceps: "Triceps", calves: "Kuiten", abs: "Buik",
};

export default function ExerciseSearch({ onSelect, onClose }) {
  const [query, setQuery] = useState("");
  const [exercises, setExercises] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) {
      setExercises([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const timeout = setTimeout(() => {
      api.get(`/exercises/search?q=${encodeURIComponent(query)}`)
        .then((data) => setExercises(data.exercises))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(timeout);
  }, [query]);

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
        <button
          onClick={onClose}
          style={{ padding: "0 16px", borderRadius: 10, border: "none", background: "none", color: "var(--text-muted)", cursor: "pointer" }}
        >
          Sluiten
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {!query.trim() && (
          <p style={{ color: "var(--text-muted)" }}>Typ om je oefeningen te doorzoeken.</p>
        )}
        {loading && <p style={{ color: "var(--text-muted)" }}>Zoeken…</p>}
        {!loading && query.trim() && exercises.length === 0 && (
          <p style={{ color: "var(--text-muted)" }}>Geen oefeningen gevonden.</p>
        )}
        {exercises.map((ex) => (
          <button
            key={ex.id}
            onClick={() => onSelect(ex.id)}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              width: "100%", textAlign: "left", padding: "12px 8px",
              background: "none", border: "none", borderBottom: "1px solid var(--text-muted)",
              color: "var(--text)", cursor: "pointer",
            }}
          >
            <div>
              <div style={{ fontWeight: 500 }}>{ex.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {MUSCLE_LABELS[ex.muscle] || ex.muscle} · {ex.is_compound ? "Compound" : "Isolatie"}
              </div>
            </div>
            {ex.logged && (
              <span style={{ fontSize: 11, color: "var(--primary)", flexShrink: 0 }}>Gelogd</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
