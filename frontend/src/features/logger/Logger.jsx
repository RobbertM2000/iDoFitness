import { useState, useRef, useCallback, useEffect } from "react";
import { api, ApiError } from "../../api/client";
import { useElapsed, useCountdown, formatMMSS } from "../../hooks/useTimer";
import ExercisePicker from "./ExercisePicker";
import ExerciseCard from "./ExerciseCard";
import RestTimer from "./RestTimer";
import WorkoutSummary from "./WorkoutSummary";

let tempIdCounter = 0;
const nextId = () => `t${++tempIdCounter}`;

function emptySet() {
  return { tempId: nextId(), weight_kg: "", reps: "", rpe: "", completed: false };
}

function newClientUuid() {
  return (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
}

async function fetchPreviousSets(exerciseId) {
  try {
    const data = await api.get(`/workouts?exercise_id=${exerciseId}&page=1`);
    const mostRecent = data.workouts[0];
    if (!mostRecent) return [];
    const match = mostRecent.exercises.find((e) => e.exercise_id === exerciseId);
    return match ? match.sets.filter((s) => !s.is_warmup) : [];
  } catch {
    return [];
  }
}

function itemsFromSuggestedWorkout(wod) {
  return wod.exercises.map((e) => {
    const suggestion = {
      weight_kg: e.weight_kg,
      reps: e.reps_max ?? e.reps_min,
      rpe: e.rpe_target_max ?? e.rpe_target_min,
      reps_min: e.reps_min,
      reps_max: e.reps_max,
      rpe_target_min: e.rpe_target_min,
      rpe_target_max: e.rpe_target_max,
    };
    return {
      tempId: nextId(),
      exercise: { id: e.exercise_id, name: e.name, is_compound: !!e.is_compound },
      previousSets: [],
      sets: Array.from({ length: e.sets }, () => ({ ...emptySet(), suggestion })),
    };
  });
}

export default function Logger({ suggestedWorkout, clearSuggestedWorkout }) {
  const [items, setItems] = useState([]);
  const [showPicker, setShowPicker] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [usingSuggestion, setUsingSuggestion] = useState(false);

  const startedAtRef = useRef(Date.now());
  const clientUuidRef = useRef(newClientUuid());
  const elapsed = useElapsed(startedAtRef.current);
  const restTimer = useCountdown();

  // Runs once on mount (§ requirement: "on mount, check if suggestedWorkout
  // exists"). WorkoutSuggestion writes to context right before switching to
  // this tab, so the prop is already populated by the time Logger mounts.
  useEffect(() => {
    if (!suggestedWorkout) return;
    const newItems = itemsFromSuggestedWorkout(suggestedWorkout);
    setItems(newItems);
    setUsingSuggestion(true);
    newItems.forEach((item) => {
      fetchPreviousSets(item.exercise.id).then((previousSets) => {
        setItems((prev) => prev.map((it) => (it.tempId === item.tempId ? { ...it, previousSets } : it)));
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addExercise = useCallback(async (exercise) => {
    setShowPicker(false);
    const item = { tempId: nextId(), exercise, sets: [emptySet()], previousSets: [] };
    setItems((prev) => [...prev, item]);
    const previousSets = await fetchPreviousSets(exercise.id);
    setItems((prev) => prev.map((it) => (it.tempId === item.tempId ? { ...it, previousSets } : it)));
  }, []);

  const updateSet = (exerciseTempId, setTempId, patch) => {
    setItems((prev) => prev.map((it) => it.tempId !== exerciseTempId ? it : {
      ...it,
      sets: it.sets.map((s) => (s.tempId === setTempId ? { ...s, ...patch } : s)),
    }));
  };

  const addSet = (exerciseTempId) => {
    setItems((prev) => prev.map((it) => {
      if (it.tempId !== exerciseTempId) return it;
      const last = it.sets[it.sets.length - 1];
      const copy = emptySet();
      if (last) { copy.weight_kg = last.weight_kg; copy.reps = last.reps; }
      return { ...it, sets: [...it.sets, copy] };
    }));
  };

  const removeSet = (exerciseTempId, setTempId) => {
    setItems((prev) => prev.map((it) => it.tempId !== exerciseTempId ? it : {
      ...it, sets: it.sets.filter((s) => s.tempId !== setTempId),
    }));
  };

  const completeSet = (exerciseTempId, setTempId) => {
    let restSeconds = 120;
    setItems((prev) => prev.map((it) => {
      if (it.tempId !== exerciseTempId) return it;
      restSeconds = it.exercise.is_compound ? 150 : 75;
      return {
        ...it,
        sets: it.sets.map((s) => {
          if (s.tempId !== setTempId) return s;
          // Untouched fields fall back to the suggestion target so a
          // suggested set can be completed in one tap.
          const filled = { ...s, completed: true };
          if (s.suggestion) {
            if (filled.weight_kg === "" && s.suggestion.weight_kg != null) {
              filled.weight_kg = String(s.suggestion.weight_kg);
            }
            if (filled.reps === "" && s.suggestion.reps != null) {
              filled.reps = String(s.suggestion.reps);
            }
            if (filled.rpe === "" && s.suggestion.rpe != null) {
              filled.rpe = String(s.suggestion.rpe);
            }
          }
          return filled;
        }),
      };
    }));
    restTimer.start(restSeconds);
  };

  const removeExercise = (exerciseTempId) => {
    setItems((prev) => prev.filter((it) => it.tempId !== exerciseTempId));
  };

  const totalCompletedSets = items.reduce(
    (sum, it) => sum + it.sets.filter((s) => s.completed).length, 0
  );

  const handleFinish = async () => {
    if (totalCompletedSets === 0) {
      const proceed = window.confirm("Er zijn geen sets gelogd. Workout toch verwijderen?");
      if (proceed) resetLogger();
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const payload = {
        client_uuid: clientUuidRef.current,
        performed_at: new Date(startedAtRef.current).toISOString(),
        duration_sec: elapsed,
        source: "manual",
        suggested_from_wod_id: usingSuggestion ? suggestedWorkout?.wod_id ?? null : null,
        exercises: items
          .map((it) => ({
            exercise_id: it.exercise.id,
            sets: it.sets
              .filter((s) => s.completed && s.weight_kg !== "" && s.reps !== "")
              .map((s) => ({
                weight_kg: Number(s.weight_kg),
                reps: Number(s.reps),
                rpe: s.rpe === "" ? undefined : Number(s.rpe),
              })),
          }))
          .filter((ex) => ex.sets.length > 0),
      };
      const data = await api.post("/workouts", payload);
      if (usingSuggestion) clearSuggestedWorkout();
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Opslaan mislukt — probeer opnieuw");
    } finally {
      setSubmitting(false);
    }
  };

  const resetLogger = () => {
    setItems([]);
    setResult(null);
    if (usingSuggestion) clearSuggestedWorkout();
    setUsingSuggestion(false);
    startedAtRef.current = Date.now();
    clientUuidRef.current = newClientUuid();
  };

  const handleClearSuggestion = () => {
    setItems([]);
    setUsingSuggestion(false);
    clearSuggestedWorkout();
  };

  if (result) {
    return <WorkoutSummary result={result} onDone={resetLogger} />;
  }

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 160px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>Workout loggen</h1>
        <span style={{ fontVariantNumeric: "tabular-nums", color: "var(--text-muted)" }}>
          {formatMMSS(elapsed)}
        </span>
      </div>

      {usingSuggestion && suggestedWorkout && (
        <div
          style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            background: "var(--surface)", border: "1px solid var(--primary)", borderRadius: 10,
            padding: "10px 12px", marginBottom: 16, fontSize: 13,
          }}
        >
          <span>
            Volgt suggestie uit{" "}
            {new Date(suggestedWorkout.date).toLocaleDateString("nl-NL", {
              day: "numeric", month: "long",
            })}
          </span>
          <button
            type="button"
            onClick={handleClearSuggestion}
            style={{
              background: "none", border: "none", color: "var(--text-muted)",
              cursor: "pointer", fontSize: 13, textDecoration: "underline", flexShrink: 0,
            }}
          >
            Wissen
          </button>
        </div>
      )}

      {items.length === 0 && (
        <p style={{ color: "var(--text-muted)", textAlign: "center", marginTop: 48 }}>
          Voeg je eerste oefening toe om te beginnen.
        </p>
      )}

      {items.map((item) => (
        <ExerciseCard
          key={item.tempId}
          item={item}
          onUpdateSet={(setId, patch) => updateSet(item.tempId, setId, patch)}
          onAddSet={() => addSet(item.tempId)}
          onRemoveSet={(setId) => removeSet(item.tempId, setId)}
          onCompleteSet={(setId) => completeSet(item.tempId, setId)}
          onRemoveExercise={() => removeExercise(item.tempId)}
        />
      ))}

      <button
        type="button"
        onClick={() => setShowPicker(true)}
        style={{
          width: "100%", height: 48, borderRadius: 10, border: "1px solid var(--primary)",
          background: "none", color: "var(--primary)", fontSize: 15, fontWeight: 600, cursor: "pointer",
          marginTop: 8,
        }}
      >
        + Oefening toevoegen
      </button>

      {error && <p style={{ color: "var(--danger)", marginTop: 12 }}>{error}</p>}

      <div
        style={{
          position: "fixed", bottom: 60, left: 0, right: 0, background: "var(--bg)",
          borderTop: "1px solid var(--text-muted)", padding: 16, zIndex: 20,
        }}
      >
        <button
          onClick={handleFinish}
          disabled={submitting}
          style={{
            width: "100%", maxWidth: 388, margin: "0 auto", display: "block",
            height: 48, borderRadius: 10, border: "none",
            background: "var(--primary)", color: "#fff", fontSize: 16, fontWeight: 600,
            opacity: submitting ? 0.6 : 1, cursor: submitting ? "not-allowed" : "pointer",
          }}
        >
          {submitting ? "Bezig…" : `Workout afronden${totalCompletedSets ? ` (${totalCompletedSets} sets)` : ""}`}
        </button>
      </div>

      <RestTimer timer={restTimer} />

      {showPicker && <ExercisePicker onSelect={addExercise} onClose={() => setShowPicker(false)} />}
    </div>
  );
}
