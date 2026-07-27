import { lazy, Suspense, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { PrimaryButton } from "../onboarding/OnboardingShell";
import WarningCard from "../../components/WarningCard";
import DashboardSkeleton, { SkeletonBlock } from "./Skeletons";

const Sparkline = lazy(() => import("./charts/Sparkline"));
const RepRangeDonut = lazy(() => import("./charts/RepRangeDonut"));
const MuscleVolumeBars = lazy(() => import("./charts/MuscleVolumeBars"));
const RpeDistributionBars = lazy(() => import("./charts/RpeDistributionBars"));

const FALLBACK_ERROR_MESSAGE = "Dashboard kon niet geladen worden. Probeer het opnieuw.";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short" });
}

function ChartFallback({ height = 100 }) {
  return <SkeletonBlock height={height} />;
}

function DeltaBadge({ value, suffix = "%" }) {
  if (value == null) {
    return <span style={{ color: "var(--text-muted)", fontSize: 14 }}>–</span>;
  }
  const up = value >= 0;
  const rounded = Math.round(Math.abs(value) * 10) / 10;
  return (
    <span style={{ color: up ? "var(--success)" : "var(--danger)", fontSize: 14, fontWeight: 600 }}>
      {up ? "▲" : "▼"} {rounded}{suffix}
    </span>
  );
}

function Card({ title, children, style }) {
  return (
    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, ...style }}>
      {title && <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px" }}>{title}</h3>}
      {children}
    </div>
  );
}

function PrimaryStatCard({ data }) {
  const isStrength = data.goal === "strength";

  if (isStrength) {
    const trained = (data.main_lift_e1rms || []).filter((l) => l.current != null);
    const top = trained[0];
    return (
      <Card style={{ marginBottom: 16 }}>
        <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "0 0 4px" }}>e1RM voortgang</p>
        {top ? (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 28, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                {top.current} kg
              </span>
              <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{top.exercise}</span>
            </div>
            <div style={{ marginBottom: 8 }}>
              {top.trend_kg_per_week != null ? (
                <DeltaBadge value={top.trend_kg_per_week} suffix=" kg/week" />
              ) : (
                <span style={{ color: "var(--text-muted)", fontSize: 13 }}>Nog niet genoeg data voor een trend</span>
              )}
            </div>
            <Suspense fallback={<ChartFallback height={40} />}>
              <Sparkline data={(top.series || []).map((s) => s.e1rm_kg)} />
            </Suspense>
          </>
        ) : (
          <p style={{ fontSize: 13, color: "var(--text-muted)", padding: "16px 0" }}>
            Nog niet genoeg data — log een paar sessies op je main lifts.
          </p>
        )}
      </Card>
    );
  }

  return (
    <Card style={{ marginBottom: 16 }}>
      <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "0 0 4px" }}>Weekvolume</p>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 28, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
          {Math.round(data.week_volume_kg).toLocaleString("nl-NL")} kg
        </span>
        <DeltaBadge value={data.week_volume_delta_pct} />
      </div>
      <Suspense fallback={<ChartFallback height={40} />}>
        <Sparkline data={data.volume_sparkline} />
      </Suspense>
    </Card>
  );
}

function SecondaryRow({ data, onSelectExercise }) {
  const isStrength = data.goal === "strength";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 16 }}>
      {isStrength ? (
        <>
          <Card title="Top lifts">
            {(data.main_lift_e1rms || []).length === 0 ? (
              <p style={{ fontSize: 13, color: "var(--text-muted)" }}>Nog niet genoeg data</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {data.main_lift_e1rms.map((lift) => (
                  <button
                    key={lift.exercise_id}
                    type="button"
                    onClick={() => onSelectExercise?.(lift.exercise_id)}
                    style={{
                      display: "block", width: "100%", textAlign: "left", padding: 0,
                      background: "none", border: "none", cursor: "pointer", color: "inherit", font: "inherit",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                      <span>{lift.exercise}</span>
                      <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                        {lift.current != null ? `${lift.current} kg` : "—"}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {lift.last_trained ? formatDate(lift.last_trained) : "Nog niet getraind"}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Card>
          <Card title="RPE-verdeling">
            <Suspense fallback={<ChartFallback height={130} />}>
              <RpeDistributionBars distribution={data.rpe_distribution} />
            </Suspense>
          </Card>
        </>
      ) : (
        <>
          <Card title="Rep-ranges">
            <Suspense fallback={<ChartFallback height={130} />}>
              <RepRangeDonut distribution={data.rep_range_distribution} />
            </Suspense>
          </Card>
          <Card title="Spiergroep-volume">
            <Suspense fallback={<ChartFallback height={130} />}>
              <MuscleVolumeBars volume={data.muscle_group_volume} />
            </Suspense>
          </Card>
        </>
      )}
    </div>
  );
}

function RecentWorkouts({ workouts, onSelect }) {
  if (!workouts || workouts.length === 0) return null;
  return (
    <Card title="Recente workouts" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {workouts.map((w) => (
          <button
            key={w.id}
            type="button"
            onClick={() => onSelect?.(w.id)}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              background: "none", border: "none", padding: 0, textAlign: "left",
              cursor: "pointer", color: "var(--text)", font: "inherit",
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>
                {w.title || "Workout"} {w.has_pr && <span style={{ color: "var(--warning)" }}>· PR</span>}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {formatDate(w.date)} · {w.exercise_count} oefeningen
              </div>
            </div>
            <span style={{ fontSize: 13, fontVariantNumeric: "tabular-nums", color: "var(--text-muted)" }}>
              {Math.round(w.tonnage_kg)} kg
            </span>
          </button>
        ))}
      </div>
    </Card>
  );
}

export default function Dashboard({ onGoToSuggestion, onGoToHistory, onSelectExercise, onOpenExerciseSearch }) {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    api
      .get("/analytics/dashboard")
      .then(setData)
      .catch((e) => {
        console.error("Dashboard laden mislukt:", e);
        const message = e instanceof ApiError && e.message && e.code !== undefined
          ? e.message
          : FALLBACK_ERROR_MESSAGE;
        setError(message);
      })
      .finally(() => setLoading(false));
  };

  // Refetches (and, via `data.goal`, switches layout entirely) whenever the
  // user's goal changes in Settings — not just on mount.
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.global_goal]);

  const dismissWarning = async (id) => {
    const previous = data.warnings || [];
    setData((d) => ({ ...d, warnings: (d.warnings || []).filter((w) => w.id !== id) }));
    try {
      await api.post(`/warnings/${id}/dismiss`);
    } catch (e) {
      setData((d) => ({ ...d, warnings: previous }));
      throw e;
    }
  };

  // TODO: no dedicated "activate deload week" flow exists yet (no
  // PeriodizationBlock UI/backend support) — for now the deload warning's
  // action button just jumps to the Suggestion tab, the most actionable
  // place to start lightening up today's session per the warning's hint.
  const handleWarningAction = (warningType) => {
    if (warningType === "deload_needed") {
      onGoToSuggestion();
    }
  };

  if (loading) {
    return <DashboardSkeleton />;
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

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 88px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px" }}>
          Welkom, {user?.display_name || user?.username}
        </h1>
        <button
          type="button"
          onClick={onOpenExerciseSearch}
          style={{
            background: "none", border: "none", color: "var(--text-muted)",
            cursor: "pointer", fontSize: 13, padding: "4px 0", flexShrink: 0,
          }}
        >
          Zoek oefening
        </button>
      </div>
      {data.streak_days > 0 ? (
        <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "0 0 20px" }}>
          🔥 {data.streak_days} {data.streak_days === 1 ? "dag" : "dagen"} op rij
        </p>
      ) : (
        <div style={{ marginBottom: 20 }} />
      )}

      {(data.warnings || []).length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {data.warnings.map((w) => (
            <WarningCard key={w.id} warning={w} onDismiss={dismissWarning} onAction={handleWarningAction} />
          ))}
        </div>
      )}

      <PrimaryStatCard data={data} />
      <SecondaryRow data={data} onSelectExercise={onSelectExercise} />

      <PrimaryButton onClick={onGoToSuggestion}>
        ⚡ Genereer workout van vandaag
      </PrimaryButton>

      <RecentWorkouts workouts={data.recent_workouts} onSelect={onGoToHistory} />
    </div>
  );
}
