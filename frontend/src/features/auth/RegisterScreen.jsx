import { useState, useRef } from "react";
import { useAuth, ApiError } from "../../context/AuthContext";
import { api } from "../../api/client";
import FieldError from "../../components/FieldError";

const USERNAME_RE = /^[a-zA-Z0-9_]+$/;

export default function RegisterScreen({ onSuccess, onSwitchToLogin }) {
  const { register } = useAuth();
  const [values, setValues] = useState({
    username: "",
    email: "",
    password: "",
    password_confirm: "",
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const usernameCheckRef = useRef(0);

  const setField = (field) => (e) =>
    setValues((v) => ({ ...v, [field]: e.target.value }));

  // Server-check on-blur (White Paper §4.2 scherm 2)
  const checkUsername = async () => {
    const u = values.username.trim();
    if (!u) return;
    const requestId = ++usernameCheckRef.current;
    try {
      const { available } = await api.get(`/auth/check-username?u=${encodeURIComponent(u)}`);
      if (requestId !== usernameCheckRef.current) return; // stale response, ignore
      if (!available) {
        setErrors((e) => ({ ...e, username: "Gebruikersnaam is al in gebruik" }));
      }
    } catch {
      // network hiccup on a blur-check isn't worth surfacing; server validates again on submit
    }
  };

  const validateClientSide = () => {
    const next = {};
    const u = values.username.trim();
    if (u.length < 3 || u.length > 30 || !USERNAME_RE.test(u)) {
      next.username = "3-30 tekens, alleen letters, cijfers en underscore";
    }
    if (!values.email.includes("@")) {
      next.email = "Ongeldig e-mailadres";
    }
    const hasLetter = /[a-zA-Z]/.test(values.password);
    const hasDigit = /[0-9]/.test(values.password);
    if (values.password.length < 8 || !hasLetter || !hasDigit) {
      next.password = "Minimaal 8 tekens met een letter en een cijfer";
    }
    if (values.password_confirm !== values.password) {
      next.password_confirm = "Wachtwoorden komen niet overeen";
    }
    return next;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const clientErrors = validateClientSide();
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      return;
    }
    setSubmitting(true);
    setErrors({});
    try {
      const user = await register(values);
      onSuccess?.(user);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setErrors({ username: "Gebruikersnaam of e-mail is al in gebruik" });
        } else {
          setErrors(err.fields && Object.keys(err.fields).length ? err.fields : { form: err.message });
        }
      } else {
        setErrors({ form: "Opslaan mislukt — probeer opnieuw" });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const isValid =
    values.username && values.email && values.password && values.password_confirm;

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 360, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 28, fontWeight: 600 }}>iDoFitness</h1>
      <p style={{ color: "var(--text-muted)", marginBottom: 24 }}>Jouw data. Jouw coach.</p>

      <label>
        Gebruikersnaam
        <input
          value={values.username}
          onChange={setField("username")}
          onBlur={checkUsername}
          autoComplete="username"
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.username}</FieldError>

      <label style={{ display: "block", marginTop: 16 }}>
        E-mail
        <input
          type="email"
          value={values.email}
          onChange={setField("email")}
          autoComplete="email"
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.email}</FieldError>

      <label style={{ display: "block", marginTop: 16 }}>
        Wachtwoord
        <input
          type="password"
          value={values.password}
          onChange={setField("password")}
          autoComplete="new-password"
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.password}</FieldError>

      <label style={{ display: "block", marginTop: 16 }}>
        Wachtwoord bevestigen
        <input
          type="password"
          value={values.password_confirm}
          onChange={setField("password_confirm")}
          autoComplete="new-password"
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.password_confirm}</FieldError>
      <FieldError>{errors.form}</FieldError>

      <button
        type="submit"
        disabled={!isValid || submitting}
        style={{
          ...buttonStyle,
          opacity: !isValid || submitting ? 0.4 : 1,
          cursor: !isValid || submitting ? "not-allowed" : "pointer",
        }}
      >
        {submitting ? "Bezig…" : "Account aanmaken"}
      </button>

      <p style={{ textAlign: "center", marginTop: 16, fontSize: 14 }}>
        Al een account?{" "}
        <button type="button" onClick={onSwitchToLogin} style={linkStyle}>
          Inloggen
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
