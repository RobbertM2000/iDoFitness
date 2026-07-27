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
import BottomNav from "./components/BottomNav";

function AuthGate() {
  const { user, loading } = useAuth();
  const { suggestedWorkout, clearSuggestedWorkout } = useWorkoutContext();
  const [authMode, setAuthMode] = useState("register"); // "register" | "login"
  const [tab, setTab] = useState("home"); // "home" | "log" | "suggestion" | "history" | "settings"

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

  return (
    <>
      {tab === "home" && (
        <Dashboard onGoToSuggestion={() => setTab("suggestion")} onGoToHistory={() => setTab("history")} />
      )}
      {tab === "log" && (
        <Logger suggestedWorkout={suggestedWorkout} clearSuggestedWorkout={clearSuggestedWorkout} />
      )}
      {tab === "suggestion" && <WorkoutSuggestion onGoToLog={() => setTab("log")} />}
      {tab === "history" && <History />}
      {tab === "settings" && <SettingsScreen onBack={() => setTab("home")} />}
      <BottomNav active={tab} onChange={setTab} />
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
