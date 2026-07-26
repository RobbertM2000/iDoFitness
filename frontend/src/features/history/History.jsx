import { useEffect, useState } from "react";
import { api } from "../../api/client";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
}

export default function History() {
  const [workouts, setWorkouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    setLoading(true);
    api.get(`/workouts?page=${page}`)
      .then((data) => { setWorkouts(data.workouts); setTotal(data.total); })
      .finally(() => setLoading(false));
  }, [page]);

  const handleDelete = async (id) => {
    if (!window.confirm("Deze workout verwijderen?")) return;
    await api.delete(`/workouts/${id}`);
    setWorkouts((prev) => prev.filter((w) => w.id !== id));
    setTotal((t) => t - 1);
  };

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 80px" }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Historie</h1>

      {loading && <p style={{ color: "var(--text-muted)" }}>Laden…</p>}
      {!loading && workouts.length === 0 && (
        <p style={{ color: "var(--text-muted)" }}>Nog geen workouts gelogd.</p>
      )}

      {workouts.map((w) => {
        const tonnage = w.exercises.reduce(
          (sum, e) => sum + e.sets.filter((s) => !s.is_warmup).reduce((s2, s) => s2 + s.weight_kg * s.reps, 0),
          0
        );
        return (
          <div key={w.id} style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600 }}>{w.title || "Workout"}</div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{formatDate(w.performed_at)}</div>
              </div>
              <button
                onClick={() => handleDelete(w.id)}
                style={{ background: "none", border: "none", color: "var(--danger)", cursor: "pointer", fontSize: 13 }}
              >
                Verwijder
              </button>
            </div>
            <div style={{ marginTop: 8, fontSize: 14, color: "var(--text-muted)" }}>
              {w.exercises.length} oefeningen · {tonnage.toFixed(0)} kg tonnage
            </div>
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 14 }}>
              {w.exercises.map((e) => (
                <li key={e.id}>
                  {e.exercise_name} — {e.sets.filter((s) => !s.is_warmup).length} sets
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      {total > 20 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 12 }}>
          <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>← Vorige</button>
          <span style={{ color: "var(--text-muted)" }}>Pagina {page}</span>
          <button disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)}>Volgende →</button>
        </div>
      )}
    </div>
  );
}
