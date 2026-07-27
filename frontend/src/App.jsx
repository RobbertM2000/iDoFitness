import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { WorkoutProvider, useWorkoutContext } from "./context/WorkoutContext";
import RegisterScreen from "./features/auth/RegisterScreen";
import LoginScreen from "./features/auth/LoginScreen";
import OnboardingWizard from "./features/onboarding/OnboardingWizard";
import Dashboard from "./features/dashboard/Dashboard";
import Logger from "./features/logger/Logger";
import History from "./features/history/History";
import WorkoutSuggestion from "./features/suggestion/WorkoutSuggestion";
import SettingsScreen from "./features/settings/SettingsScreen";
import ExerciseDetail from "./features/exercise/ExerciseDetail";
import ExerciseSearch from "./features/exercise/ExerciseSearch";
import BottomNav from "./components/BottomNav";

function AuthGate() {
  const { user, loading } = useAuth();
  const { suggestedWorkout, clearSuggestedWorkout } = useWorkoutContext();
  const [authMode, setAuthMode] = useState("register"); // "register" | "login"
  const [tab, setTab] = useState("home"); // "home" | "log" | "suggestion" | "history" | "settings"
  // ExerciseDetail is a detail view reached FROM other screens, not a
  // bottom-nav tab itself — tracked separately so it can overlay whichever
  // tab launched it and return there on back.
  const [selectedExerciseId, setSelectedExerciseId] = useState(null);
  const [showExerciseSearch, setShowExerciseSearch] = useState(false);

  if (loading) {
    return <p style={{ padding: 24 }}>Laden…</p>;
  }

  if (!user) {
    return authMode === "register" ? (
      <RegisterScreen onSwitchToLogin={() => setAuthMode("login")} />
    ) : (
      <LoginScreen onSwitchToRegister={() => setAuthMode("register")} />
    );
  }

  if (!user.onboarding_completed) {
    return <OnboardingWizard />;
  }

  const handleTabChange = (nextTab) => {
    setSelectedExerciseId(null);
    setTab(nextTab);
  };

  return (
    <>
      {selectedExerciseId ? (
        <ExerciseDetail
          exerciseId={selectedExerciseId}
          onBack={() => setSelectedExerciseId(null)}
          onGoToLog={() => {
            setSelectedExerciseId(null);
            setTab("log");
          }}
        />
      ) : (
        <>
          {tab === "home" && (
            <Dashboard
              onGoToSuggestion={() => setTab("suggestion")}
              onGoToHistory={() => setTab("history")}
              onSelectExercise={setSelectedExerciseId}
              onOpenExerciseSearch={() => setShowExerciseSearch(true)}
            />
          )}
          {tab === "log" && (
            <Logger suggestedWorkout={suggestedWorkout} clearSuggestedWorkout={clearSuggestedWorkout} />
          )}
          {tab === "suggestion" && <WorkoutSuggestion onGoToLog={() => setTab("log")} />}
          {tab === "history" && <History onSelectExercise={setSelectedExerciseId} />}
          {tab === "settings" && <SettingsScreen onBack={() => setTab("home")} />}
        </>
      )}
      <BottomNav active={tab} onChange={handleTabChange} />
      {showExerciseSearch && (
        <ExerciseSearch
          onClose={() => setShowExerciseSearch(false)}
          onSelect={(exerciseId) => {
            setShowExerciseSearch(false);
            setSelectedExerciseId(exerciseId);
          }}
        />
      )}
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <WorkoutProvider>
        <AuthGate />
      </WorkoutProvider>
    </AuthProvider>
  );
}
