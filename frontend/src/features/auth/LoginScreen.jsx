import { useState } from "react";
import { useAuth, ApiError } from "../../context/AuthContext";
import FieldError from "../../components/FieldError";

export default function LoginScreen({ onSuccess, onSwitchToRegister }) {
  const { login } = useAuth();
  const [values, setValues] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const setField = (field) => (e) =>
    setValues((v) => ({ ...v, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const user = await login(values);
      onSuccess?.(user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Inloggen mislukt — probeer opnieuw");
    } finally {
      setSubmitting(false);
    }
  };

  const isValid = values.username && values.password;

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 360, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 28, fontWeight: 600 }}>iDoFitness</h1>
      <p style={{ color: "var(--text-muted)", marginBottom: 24 }}>Welkom terug.</p>

      <label>
        Gebruikersnaam of e-mail
        <input value={values.username} onChange={setField("username")} style={inputStyle} />
      </label>

      <label style={{ display: "block", marginTop: 16 }}>
        Wachtwoord
        <input
          type="password"
          value={values.password}
          onChange={setField("password")}
          autoComplete="current-password"
          style={inputStyle}
        />
      </label>
      <FieldError>{error}</FieldError>

      <button
        type="submit"
        disabled={!isValid || submitting}
        style={{
          ...buttonStyle,
          opacity: !isValid || submitting ? 0.4 : 1,
          cursor: !isValid || submitting ? "not-allowed" : "pointer",
        }}
      >
        {submitting ? "Bezig…" : "Inloggen"}
      </button>

      <p style={{ textAlign: "center", marginTop: 16, fontSize: 14 }}>
        Nog geen account?{" "}
        <button type="button" onClick={onSwitchToRegister} style={linkStyle}>
          Account aanmaken
        </button>
      </p>
    </form>
  );
}

const inputStyle = {
  display: "block",
  width: "100%",
  height: 44,
  marginTop: 4,
  padding: "0 12px",
  border: "1px solid var(--text-muted)",
  borderRadius: 10,
  background: "var(--surface)",
  color: "var(--text)",
  fontSize: 16,
};

const buttonStyle = {
  width: "100%",
  height: 48,
  marginTop: 24,
  border: "none",
  borderRadius: 10,
  background: "var(--primary)",
  color: "#fff",
  fontSize: 16,
  fontWeight: 600,
};

const linkStyle = {
  background: "none",
  border: "none",
  color: "var(--primary)",
  fontWeight: 600,
  cursor: "pointer",
  padding: 0,
};
