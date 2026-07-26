import { createContext, useContext, useState, useCallback } from "react";

const WorkoutContext = createContext(null);

const STORAGE_KEY = "suggestedWorkout";

function readStoredWorkout() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
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

  return (
    <WorkoutContext.Provider value={{ suggestedWorkout, setSuggestedWorkout, clearSuggestedWorkout }}>
      {children}
    </WorkoutContext.Provider>
  );
}

export function useWorkoutContext() {
  const ctx = useContext(WorkoutContext);
  if (!ctx) throw new Error("useWorkoutContext must be used within WorkoutProvider");
  return ctx;
}
