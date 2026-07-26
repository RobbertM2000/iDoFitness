import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { useWorkoutContext } from "../../context/WorkoutContext";

function formatRest(sec) {
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  return s === 0 ? `${min} min` : `${min}:${s.toString().padStart(2, "0")} min`;
}

function formatRepsRpe(e) {
  const reps = e.reps_min === e.reps_max ? `${e.reps_min}` : `${e.reps_min}-${e.reps_max}`;
  const rpe = e.rpe_target_min === e.rpe_target_max ? `${e.rpe_target_min}` : `${e.rpe_target_min}-${e.rpe_target_max}`;
  return `${e.sets} × ${reps} reps @ RPE ${rpe}`;
}

export default function WorkoutSuggestion({ onGoToLog }) {
  const [wod, setWod] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { setSuggestedWorkout } = useWorkoutContext();

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .get("/workout-suggestion")
      .then(setWod)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Kon geen workout genereren"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p style={{ padding: 24, color: "var(--text-muted)" }}>Workout genereren…</p>;
  }

  if (error) {
    return <p style={{ padding: 24, color: "var(--danger)" }}>{error}</p>;
  }

  if (!wod || wod.exercises.length === 0) {
    return (
      <div style={{ maxWidth: 420, margin: "0 auto", padding: "24px 16px 80px" }}>
        <p style={{ color: "var(--text-muted)" }}>
          Geen oefeningen beschikbaar. Check je apparatuur-instellingen of log eerst een paar workouts.
        </p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 88px" }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>{wod.title}</h1>
      <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
        ~{wod.estimated_duration_min} min
      </p>

      {wod.cold_start && (
        <div
          style={{
            background: "var(--warning)", color: "#fff", borderRadius: 12,
            padding: 12, marginBottom: 16, fontSize: 14,
          }}
        >
          Nog geen historie — log je eerste workout voor persoonlijke aanbevelingen.
        </div>
      )}

      <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Warming-up</div>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{wod.warmup.general}</div>
        {wod.warmup.ramp_sets.length > 0 && (
          <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13, color: "var(--text-muted)" }}>
            {wod.warmup.ramp_sets.map((r, i) => (
              <li key={i}>
                {r.weight_kg} kg × {r.reps} ({r.pct}%)
              </li>
            ))}
          </ul>
        )}
        {wod.warmup.note && (
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 6 }}>{wod.warmup.note}</div>
        )}
      </div>

      {wod.exercises.map((e) => (
        <div
          key={e.exercise_id}
          style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 12 }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <h3 style={{ fontSize: 17, fontWeight: 600, margin: 0 }}>
              {e.order}. {e.name}
            </h3>
            {e.provisional && (
              <span style={{ fontSize: 11, color: "var(--warning)", fontWeight: 600, whiteSpace: "nowrap" }}>
                VOORLOPIG
              </span>
            )}
          </div>
          <div style={{ fontSize: 15, marginTop: 6 }}>{formatRepsRpe(e)}</div>
          <div style={{ fontSize: 14, color: "var(--text)", marginTop: 2 }}>
            {e.weight_kg != null ? `${e.weight_kg} kg` : "Kies zelf een startgewicht"}
            <span style={{ color: "var(--text-muted)" }}> · rust {formatRest(e.rest_sec)}</span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 8, marginBottom: 0 }}>
            {e.reason}
          </p>
        </div>
      ))}

      <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Cooldown</div>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{wod.cooldown}</div>
      </div>

      <button
        onClick={() => {
          setSuggestedWorkout(wod);
          onGoToLog();
        }}
        style={{
          width: "100%", padding: 14, borderRadius: 10, border: "none",
          background: "var(--primary)", color: "#fff", fontSize: 16, fontWeight: 600,
          cursor: "pointer",
        }}
      >
        Start deze workout
      </button>
    </div>
  );
}
