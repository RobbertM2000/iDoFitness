import { createContext, useContext, useState, useCallback } from "react";

const WorkoutContext = createContext(null);

const STORAGE_KEY = "suggestedWorkout";
const ACTIVE_DRAFT_KEY = "activeWorkout";

// White Paper §16 edge case #2 — a draft older than this is no longer
// offered as a plain "resume", only as a save-as-incomplete/discard choice.
export const DRAFT_STALE_MS = 12 * 60 * 60 * 1000;

function readStoredWorkout() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function readStoredActiveDraft() {
  try {
    const raw = localStorage.getItem(ACTIVE_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // A draft with no exercises isn't worth resuming (edge case: nothing
    // was ever added before the user navigated away) — treat it as absent.
    return parsed && Array.isArray(parsed.exercises) && parsed.exercises.length > 0 ? parsed : null;
  } catch {
    return null;
  }
}

export function WorkoutProvider({ children }) {
  const [suggestedWorkout, setSuggestedWorkoutState] = useState(readStoredWorkout);

  const setSuggestedWorkout = useCallback((wod) => {
    setSuggestedWorkoutState(wod);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(wod));
    } catch {
      // localStorage unavailable (private mode, quota) — context state still works
    }
  }, []);

  const clearSuggestedWorkout = useCallback(() => {
    setSuggestedWorkoutState(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  // activeDraft: the live, currently-editable in-progress workout — lives
  // here (above Logger in the tree) specifically so it survives Logger
  // unmounting when the bottom nav switches tabs (White Paper §7.2).
  // pendingDraft: a draft found in localStorage when the app first loaded,
  // awaiting an explicit Resume/Discard decision — kept separate from
  // activeDraft so Logger never silently auto-resumes without asking.
  const [activeDraft, setActiveDraftState] = useState(null);
  const [pendingDraft, setPendingDraftState] = useState(readStoredActiveDraft);

  const saveActiveDraft = useCallback((draft) => {
    setActiveDraftState(draft);
    try {
      if (draft && draft.exercises && draft.exercises.length > 0) {
        localStorage.setItem(ACTIVE_DRAFT_KEY, JSON.stringify(draft));
      } else {
        localStorage.removeItem(ACTIVE_DRAFT_KEY);
      }
    } catch {
      // ignore
    }
  }, []);

  const clearActiveDraft = useCallback(() => {
    setActiveDraftState(null);
    setPendingDraftState(null);
    try {
      localStorage.removeItem(ACTIVE_DRAFT_KEY);
    } catch {
      // ignore
    }
  }, []);

  const resumePendingDraft = useCallback(() => {
    setActiveDraftState(pendingDraft);
    setPendingDraftState(null);
  }, [pendingDraft]);

  const discardPendingDraft = useCallback(() => {
    setPendingDraftState(null);
    try {
      localStorage.removeItem(ACTIVE_DRAFT_KEY);
    } catch {
      // ignore
    }
  }, []);

  return (
    <WorkoutContext.Provider
      value={{
        suggestedWorkout, setSuggestedWorkout, clearSuggestedWorkout,
        activeDraft, saveActiveDraft, clearActiveDraft,
        pendingDraft, resumePendingDraft, discardPendingDraft,
      }}
    >
      {children}
    </WorkoutContext.Provider>
  );
}

export function useWorkoutContext() {
  const ctx = useContext(WorkoutContext);
  if (!ctx) throw new Error("useWorkoutContext must be used within WorkoutProvider");
  return ctx;
}
