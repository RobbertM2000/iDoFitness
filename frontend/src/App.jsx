import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import RegisterScreen from "./features/auth/RegisterScreen";
import LoginScreen from "./features/auth/LoginScreen";

function AuthGate() {
  const { user, loading, logout } = useAuth();
  const [mode, setMode] = useState("register"); // "register" | "login"

  if (loading) {
    return <p style={{ padding: 24 }}>Laden…</p>;
  }

  if (user) {
    return (
      <main style={{ padding: 24 }}>
        <h1>Welkom, {user.display_name || user.username}</h1>
        <p style={{ color: "var(--text-muted)" }}>
          Je bent ingelogd. Onboarding en dashboard volgen in de volgende stap.
        </p>
        <button onClick={logout} style={{ marginTop: 16 }}>
          Uitloggen
        </button>
      </main>
    );
  }

  return mode === "register" ? (
    <RegisterScreen onSwitchToLogin={() => setMode("login")} />
  ) : (
    <LoginScreen onSwitchToRegister={() => setMode("register")} />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
