import { lazy, Suspense, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { useWorkoutContext } from "../../context/WorkoutContext";
import { PrimaryButton } from "../onboarding/OnboardingShell";
import { SkeletonBlock } from "../dashboard/Skeletons";

const ProgressionChart = lazy(() => import("./charts/ProgressionChart"));

const FALLBACK_ERROR_MESSAGE = "Geschiedenis kon niet geladen worden. Probeer het opnieuw.";

const MUSCLE_LABELS = {
  chest: "Borst", back: "Rug", quads: "Quads", hamstrings: "Hamstrings",
  glutes: "Glutes", shoulders: "Schouders", biceps: "Biceps",
  triceps: "Triceps", calves: "Kuiten", abs: "Buik",
};

const PR_LABELS = { weight: "Gewicht", reps: "Reps", e1rm: "e1RM", tonnage: "Tonnage" };

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
}

function StatCard({ label, value, unit }) {
  return (
    <div style={{ background: "var(--surface)", borderRadius: 12, padding: "12px 10px", textAlign: "center" }}>
      <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
        {value != null ? `${value}${unit ? ` ${unit}` : ""}` : "—"}
      </div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{label}</div>
    </div>
  );
}

export default function ExerciseDetail({ exerciseId, onBack, onGoToLog }) {
  const { setSuggestedWorkout } = useWorkoutContext();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState("e1rm");

  const load = () => {
    setLoading(true);
    setError("");
    api
      .get(`/analytics/progression?exercise_id=${exerciseId}`)
      .then((d) => {
        setData(d);
        const hasE1rm = d.data_points.some((p) => p.e1rm_kg != null);
        setMetric(hasE1rm ? "e1rm" : "weight");
      })
      .catch((e) => {
        console.error("Oefening-geschiedenis laden mislukt:", e);
        const message = e instanceof ApiError && e.message && e.code !== undefined
          ? e.message
          : FALLBACK_ERROR_MESSAGE;
        setError(message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exerciseId]);

  const handleLogExercise = () => {
    const points = data.data_points;
    const last = points[points.length - 1];
    const wod = {
      date: new Date().toISOString().slice(0, 10),
      goal: "hypertrophy",
      wod_id: `manual-log:${exerciseId}`,
      exercises: [{
        exercise_id: exerciseId,
        name: data.exercise_name,
        is_compound: data.is_compound,
        sets: 3,
        reps_min: last?.reps ?? null,
        reps_max: last?.reps ?? null,
        rpe_target_min: 7,
        rpe_target_max: 8,
        weight_kg: last?.weight_kg ?? null,
      }],
    };
    setSuggestedWorkout(wod);
    onGoToLog();
  };

  if (loading) {
    return (
      <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 88px" }}>
        <SkeletonBlock width="50%" height={22} style={{ marginBottom: 24 }} />
        <SkeletonBlock height={220} style={{ marginBottom: 16 }} />
        <SkeletonBlock height={70} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <p style={{ color: "var(--danger)", marginBottom: 16 }}>{error}</p>
        <button
          type="button"
          onClick={load}
          style={{
            padding: "10px 24px", borderRadius: 10, border: "none",
            background: "var(--primary)", color: "#fff", fontSize: 15, fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Opnieuw proberen
        </button>
      </div>
    );
  }

  const hasE1rm = data.data_points.some((p) => p.e1rm_kg != null);
  const recentPoints = [...data.data_points].reverse().slice(0, 10);
  const pr = data.personal_records || {};

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 88px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <button
          type="button"
          onClick={onBack}
          aria-label="Terug"
          style={{
            background: "none", border: "none", color: "var(--text-muted)",
            cursor: "pointer", fontSize: 20, padding: 0, lineHeight: 1,
          }}
        >
          ‹
        </button>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0, flex: 1 }}>{data.exercise_name}</h1>
        {data.muscle && (
          <span
            style={{
              fontSize: 12, color: "var(--text-muted)", border: "1px solid var(--text-muted)",
              borderRadius: 999, padding: "3px 10px", flexShrink: 0,
            }}
          >
            {MUSCLE_LABELS[data.muscle] || data.muscle}
          </span>
        )}
      </div>

      {data.data_points.length === 0 ? (
        <div style={{ textAlign: "center", padding: "48px 16px" }}>
          <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>
            Je hebt deze oefening nog niet gelogd.
          </p>
          <PrimaryButton onClick={handleLogExercise}>Log deze oefening</PrimaryButton>
        </div>
      ) : (
        <>
          {data.provisional && (
            <div
              style={{
                background: "var(--warning)", color: "#fff", borderRadius: 12,
                padding: 12, marginBottom: 16, fontSize: 13,
              }}
            >
              Nog voorlopig — na 5 sessies wordt je trend betrouwbaar.
            </div>
          )}

          <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
            {hasE1rm && (
              <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                {[["e1rm", "e1RM"], ["weight", "Gewicht"]].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setMetric(key)}
                    style={{
                      padding: "6px 14px", borderRadius: 999, fontSize: 13, cursor: "pointer",
                      border: `1px solid ${metric === key ? "var(--primary)" : "var(--text-muted)"}`,
                      background: metric === key ? "var(--primary)" : "transparent",
                      color: metric === key ? "#fff" : "var(--text)",
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
            <Suspense fallback={<SkeletonBlock height={220} />}>
              <ProgressionChart dataPoints={data.data_points} metric={metric} regression={data.regression} />
            </Suspense>
            {data.regression && metric === "e1rm" && (
              <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "8px 0 0", textAlign: "right" }}>
                <span style={{ color: "var(--success)" }}>┄</span> verwacht over 2 weken: {data.regression.forecast_2weeks} kg
              </p>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 16 }}>
            <StatCard label="e1RM" value={pr.e1rm?.value} unit="kg" />
            <StatCard label="Gewicht" value={pr.weight?.value} unit="kg" />
            <StatCard label="Reps" value={pr.reps?.value} />
            <StatCard label="Tonnage" value={pr.tonnage?.value} unit="kg" />
          </div>

          <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px" }}>Recente sets</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {recentPoints.map((p) => (
                <div key={p.date} style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                  <span style={{ color: "var(--text-muted)" }}>{formatDate(p.date)}</span>
                  <span style={{ fontVariantNumeric: "tabular-nums" }}>
                    {p.weight_kg} kg × {p.reps}
                    {p.is_pr && <span style={{ color: "var(--success)", fontWeight: 600 }}> · PR</span>}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <PrimaryButton onClick={handleLogExercise}>Log deze oefening</PrimaryButton>
        </>
      )}
    </div>
  );
}
