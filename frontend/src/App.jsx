import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import RegisterScreen from "./features/auth/RegisterScreen";
import LoginScreen from "./features/auth/LoginScreen";
import OnboardingWizard from "./features/onboarding/OnboardingWizard";
import Logger from "./features/logger/Logger";
import History from "./features/history/History";
import WorkoutSuggestion from "./features/suggestion/WorkoutSuggestion";
import BottomNav from "./components/BottomNav";

function HomeScreen({ user, logout }) {
  return (
    <main style={{ maxWidth: 420, margin: "0 auto", padding: "24px 16px 80px" }}>
      <h1>Welkom, {user.display_name || user.username}</h1>
      <p style={{ color: "var(--text-muted)" }}>
        Doel: {user.global_goal === "strength" ? "Kracht" : "Hypertrofie"} · {user.experience}
      </p>
      <p style={{ color: "var(--text-muted)" }}>
        Gebruik de Log-tab hieronder om een workout te loggen.
      </p>
      <button onClick={logout} style={{ marginTop: 16 }}>
        Uitloggen
      </button>
    </main>
  );
}

function AuthGate() {
  const { user, loading, logout } = useAuth();
  const [authMode, setAuthMode] = useState("register"); // "register" | "login"
  const [tab, setTab] = useState("home"); // "home" | "log" | "history"

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
      {tab === "home" && <HomeScreen user={user} logout={logout} />}
      {tab === "log" && <Logger />}
      {tab === "suggestion" && <WorkoutSuggestion onGoToLog={() => setTab("log")} />}
      {tab === "history" && <History />}
      <BottomNav active={tab} onChange={setTab} />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
