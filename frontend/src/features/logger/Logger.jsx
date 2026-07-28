import { useState, useRef, useCallback, useEffect } from "react";
import { api, ApiError } from "../../api/client";
import { useElapsed, useCountdown, formatMMSS } from "../../hooks/useTimer";
import { useWorkoutContext, DRAFT_STALE_MS } from "../../context/WorkoutContext";
import ExercisePicker from "./ExercisePicker";
import ExerciseCard from "./ExerciseCard";
import RestTimer from "./RestTimer";
import WorkoutSummary from "./WorkoutSummary";
import ResumeDraftDialog from "./ResumeDraftDialog";

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

// --- draft <-> items conversion (White Paper §7.2) --------------------
// previousSets is deliberately left out of the persisted shape: it's
// read-only context fetched from history, not user input, so it's cheap
// to re-fetch after a resume rather than duplicate into localStorage.

function itemsToDraftExercises(items) {
  return items.map((it) => ({
    exercise: { id: it.exercise.id, name: it.exercise.name, is_compound: !!it.exercise.is_compound },
    sets: it.sets.map((s) => ({
      weight_kg: s.weight_kg, reps: s.reps, rpe: s.rpe, completed: s.completed,
      suggestion: s.suggestion || null,
    })),
  }));
}

function itemsFromDraftExercises(draftExercises) {
  return draftExercises.map((ex) => ({
    tempId: nextId(),
    exercise: ex.exercise,
    previousSets: [],
    sets: ex.sets.map((s) => ({
      tempId: nextId(),
      weight_kg: s.weight_kg ?? "",
      reps: s.reps ?? "",
      rpe: s.rpe ?? "",
      completed: !!s.completed,
      suggestion: s.suggestion || undefined,
    })),
  }));
}

function draftHasCompletedSets(draft) {
  return draft.exercises.some((ex) => ex.sets.some((s) => s.completed));
}

function refreshPreviousSets(items, setItems) {
  items.forEach((item) => {
    fetchPreviousSets(item.exercise.id).then((previousSets) => {
      setItems((prev) => prev.map((it) => (it.tempId === item.tempId ? { ...it, previousSets } : it)));
    });
  });
}

export default function Logger({ suggestedWorkout, clearSuggestedWorkout }) {
  const {
    activeDraft, saveActiveDraft, clearActiveDraft,
    pendingDraft, resumePendingDraft, discardPendingDraft,
  } = useWorkoutContext();

  const [items, setItems] = useState(() => (activeDraft ? itemsFromDraftExercises(activeDraft.exercises) : []));
  const [showPicker, setShowPicker] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [usingSuggestion, setUsingSuggestion] = useState(() => activeDraft?.using_suggestion ?? false);
  const [savingIncomplete, setSavingIncomplete] = useState(false);

  const startedAtRef = useRef(activeDraft ? Date.parse(activeDraft.started_at) : Date.now());
  const clientUuidRef = useRef(activeDraft?.client_uuid || newClientUuid());
  const elapsed = useElapsed(startedAtRef.current);
  const restTimer = useCountdown(activeDraft?.rest_target_at ?? null);

  // Runs once on mount (§ requirement: "on mount, check if suggestedWorkout
  // exists"). WorkoutSuggestion writes to context right before switching to
  // this tab, so the prop is already populated by the time Logger mounts.
  // Skipped while a draft (resumed or still pending a Resume/Discard
  // decision) is in play, so an incoming suggestion never races with —
  // or silently overwrites — older in-progress work (White Paper §7.2).
  useEffect(() => {
    if (!suggestedWorkout || pendingDraft || activeDraft) return;
    const newItems = itemsFromSuggestedWorkout(suggestedWorkout);
    setItems(newItems);
    setUsingSuggestion(true);
    refreshPreviousSets(newItems, setItems);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A draft resumed via lazy init above (i.e. Logger remounted after a tab
  // switch while a draft was already active) still needs its "previous
  // sets" context re-fetched, same as addExercise does for a brand-new one.
  useEffect(() => {
    if (!activeDraft) return;
    refreshPreviousSets(items, setItems);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // §16 edge case #2: a stale (>12h) draft with zero completed sets has
  // nothing worth offering to save — discard it quietly instead of
  // interrupting the user with a dialog for an effectively empty draft.
  useEffect(() => {
    if (pendingDraft && Date.now() - Date.parse(pendingDraft.started_at) > DRAFT_STALE_MS) {
      if (!draftHasCompletedSets(pendingDraft)) discardPendingDraft();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // White Paper §7.2 — persist the full draft on every change so it
  // survives Logger unmounting (switching tabs) or the page reloading
  // entirely (backgrounded tab reclaimed, browser closed and reopened).
  // Skipped for an empty logger (nothing added yet) so navigating away
  // before adding anything doesn't leave a pointless draft behind.
  useEffect(() => {
    if (items.length === 0) return;
    saveActiveDraft({
      client_uuid: clientUuidRef.current,
      started_at: new Date(startedAtRef.current).toISOString(),
      using_suggestion: usingSuggestion,
      suggestion_snapshot: usingSuggestion && suggestedWorkout
        ? { date: suggestedWorkout.date, wod_id: suggestedWorkout.wod_id }
        : null,
      rest_target_at: restTimer.targetAt,
      exercises: itemsToDraftExercises(items),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, usingSuggestion, restTimer.targetAt]);

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
      clearActiveDraft();
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
    restTimer.stop();
    clearActiveDraft();
  };

  const handleClearSuggestion = () => {
    setItems([]);
    setUsingSuggestion(false);
    clearSuggestedWorkout();
    clearActiveDraft();
  };

  const handleResumeDraft = () => {
    const draft = pendingDraft;
    const restoredItems = itemsFromDraftExercises(draft.exercises);
    setError("");
    resumePendingDraft();
    setItems(restoredItems);
    setUsingSuggestion(!!draft.using_suggestion);
    startedAtRef.current = Date.parse(draft.started_at);
    clientUuidRef.current = draft.client_uuid || newClientUuid();
    if (draft.rest_target_at && draft.rest_target_at > Date.now()) {
      restTimer.restoreTarget(draft.rest_target_at);
    }
    refreshPreviousSets(restoredItems, setItems);
  };

  const handleDiscardDraft = () => {
    setError("");
    discardPendingDraft();
  };

  const handleSaveIncomplete = async () => {
    if (!pendingDraft) return;
    const exercises = pendingDraft.exercises
      .map((ex) => ({
        exercise_id: ex.exercise.id,
        sets: ex.sets
          .filter((s) => s.completed && s.weight_kg !== "" && s.reps !== "")
          .map((s) => ({
            weight_kg: Number(s.weight_kg),
            reps: Number(s.reps),
            rpe: s.rpe === "" || s.rpe == null ? undefined : Number(s.rpe),
          })),
      }))
      .filter((ex) => ex.sets.length > 0);

    if (exercises.length === 0) {
      discardPendingDraft();
      return;
    }

    setSavingIncomplete(true);
    setError("");
    try {
      await api.post("/workouts", {
        client_uuid: pendingDraft.client_uuid,
        performed_at: new Date(pendingDraft.started_at).toISOString(),
        source: "manual",
        title: "Onvolledige workout",
        notes: "Automatisch opgeslagen: workout werd niet binnen 12 uur afgerond en niet hervat.",
        suggested_from_wod_id: pendingDraft.suggestion_snapshot?.wod_id ?? null,
        exercises,
      });
      discardPendingDraft();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Opslaan mislukt — probeer opnieuw");
    } finally {
      setSavingIncomplete(false);
    }
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

      {pendingDraft && (
        <ResumeDraftDialog
          draft={pendingDraft}
          saving={savingIncomplete}
          error={error}
          onResume={handleResumeDraft}
          onDiscard={handleDiscardDraft}
          onSaveIncomplete={handleSaveIncomplete}
        />
      )}
    </div>
  );
}
