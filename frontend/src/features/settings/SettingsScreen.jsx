import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { inputStyle, PrimaryButton, OptionCard } from "../onboarding/OnboardingShell";
import FieldError from "../../components/FieldError";
import Spinner from "../../components/Spinner";
import Toast from "../../components/Toast";

const EXPERIENCE_OPTIONS = [
  { value: "beginner", label: "Beginner", sub: "<1 jaar" },
  { value: "intermediate", label: "Intermediate", sub: "1-3 jaar" },
  { value: "advanced", label: "Advanced", sub: "3+ jaar" },
];

const DURATIONS = [30, 45, 60, 75, 90];

const LOCATIONS = [
  { value: "gym", label: "Sportschool" },
  { value: "home", label: "Thuis" },
  { value: "both", label: "Beide" },
];

const sectionLabelStyle = { marginTop: 24, marginBottom: 8, fontSize: 14, fontWeight: 500 };

function choiceCardStyle(selected) {
  return {
    padding: 16,
    borderRadius: 12,
    border: `2px solid ${selected ? "var(--primary)" : "var(--text-muted)"}`,
    background: selected ? "var(--surface)" : "transparent",
    color: "var(--text)",
    cursor: "pointer",
    textAlign: "left",
  };
}

function pillStyle(selected) {
  return {
    padding: "8px 14px",
    borderRadius: 999,
    border: `1px solid ${selected ? "var(--primary)" : "var(--text-muted)"}`,
    background: selected ? "var(--primary)" : "transparent",
    color: selected ? "#fff" : "var(--text)",
    cursor: "pointer",
    fontSize: 14,
  };
}

const stepperButtonStyle = {
  width: 40,
  height: 40,
  borderRadius: 10,
  border: "1px solid var(--text-muted)",
  background: "var(--surface)",
  color: "var(--text)",
  fontSize: 20,
  cursor: "pointer",
};

const backButtonStyle = {
  display: "flex",
  alignItems: "center",
  gap: 4,
  background: "none",
  border: "none",
  color: "var(--text-muted)",
  cursor: "pointer",
  padding: 0,
  marginBottom: 12,
  fontSize: 14,
};

function needsEquipmentFor(location) {
  return location === "home" || location === "both";
}

function validate(form) {
  const fields = {};
  if (!form.global_goal) fields.global_goal = "Kies hypertrofie of kracht";
  if (!form.experience) fields.experience = "Kies een ervaringsniveau";
  if (!form.days_per_week || form.days_per_week < 1 || form.days_per_week > 7) {
    fields.days_per_week = "1-7 dagen";
  }
  if (!form.session_minutes) fields.session_minutes = "Ongeldige sessieduur";
  if (!form.training_location) fields.training_location = "Kies sportschool, thuis of beide";
  if (needsEquipmentFor(form.training_location) && (form.equipment || []).length === 0) {
    fields.equipment = "Kies minstens één apparatuur-optie";
  }
  return fields;
}

export default function SettingsScreen({ onBack }) {
  const { setUser } = useAuth();
  const [form, setForm] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [equipmentOptions, setEquipmentOptions] = useState([]);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [showToast, setShowToast] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/profile")
      .then((data) => {
        if (cancelled) return;
        const user = data.user;
        setForm({
          display_name: user.display_name || "",
          global_goal: user.global_goal || "",
          experience: user.experience || "",
          days_per_week: user.days_per_week || 4,
          session_minutes: user.session_minutes || null,
          training_location: user.training_location || "",
          equipment: user.equipment || [],
        });
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err instanceof ApiError ? err.message : "Profiel laden mislukt");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const needsEquipment = form ? needsEquipmentFor(form.training_location) : false;

  useEffect(() => {
    if (needsEquipment && equipmentOptions.length === 0) {
      api.get("/equipment").then((data) => setEquipmentOptions(data.equipment));
    }
  }, [needsEquipment, equipmentOptions.length]);

  const update = (patch) => setForm((f) => ({ ...f, ...patch }));

  const toggleEquipment = (name) => {
    const current = form.equipment || [];
    const next = current.includes(name) ? current.filter((n) => n !== name) : [...current, name];
    update({ equipment: next });
  };

  const handleSave = async () => {
    const fieldErrors = validate(form);
    if (Object.keys(fieldErrors).length) {
      setErrors(fieldErrors);
      return;
    }
    setErrors({});
    setSaving(true);
    try {
      const data = await api.patch("/profile", {
        display_name: form.display_name.trim() || null,
        global_goal: form.global_goal,
        experience: form.experience,
        days_per_week: form.days_per_week,
        session_minutes: form.session_minutes,
        training_location: form.training_location,
        equipment: form.training_location === "gym" ? [] : form.equipment,
      });
      setUser(data.user);
      setShowToast(true);
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields || {}).length) {
        setErrors(err.fields);
      } else {
        setErrors({
          _general: err instanceof ApiError ? err.message : "Opslaan mislukt — probeer opnieuw",
        });
      }
    } finally {
      setSaving(false);
    }
  };

  if (loadError) {
    return (
      <div style={{ maxWidth: 400, margin: "0 auto", padding: 24 }}>
        <FieldError>{loadError}</FieldError>
      </div>
    );
  }

  if (!form) {
    return (
      <div style={{ maxWidth: 400, margin: "0 auto", padding: 24, textAlign: "center" }}>
        <Spinner />
        <p style={{ color: "var(--text-muted)", marginTop: 12 }}>Profiel laden…</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 400, margin: "0 auto", padding: "24px 24px 96px" }}>
      {onBack && (
        <button type="button" onClick={onBack} style={backButtonStyle}>
          <span aria-hidden="true">‹</span> Terug
        </button>
      )}

      <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>Instellingen</h1>
      <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>Werk je profiel bij.</p>

      <label>
        Naam (optioneel)
        <input
          value={form.display_name}
          onChange={(e) => update({ display_name: e.target.value })}
          style={inputStyle}
        />
      </label>

      <p style={sectionLabelStyle}>Trainingsdoel</p>
      <OptionCard
        icon="💪"
        title="Hypertrofie"
        subtitle="Maximale spiergroei. Focus op volume, 6-15 reps."
        selected={form.global_goal === "hypertrophy"}
        onClick={() => update({ global_goal: "hypertrophy" })}
      />
      <OptionCard
        icon="🏋️"
        title="Kracht"
        subtitle="Maximale kracht. Focus op 1RM, 1-6 reps."
        selected={form.global_goal === "strength"}
        onClick={() => update({ global_goal: "strength" })}
      />
      <FieldError>{errors.global_goal}</FieldError>

      <p style={sectionLabelStyle}>Trainingservaring</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {EXPERIENCE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => update({ experience: opt.value })}
            style={choiceCardStyle(form.experience === opt.value)}
          >
            <div style={{ fontWeight: 600 }}>{opt.label}</div>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{opt.sub}</div>
          </button>
        ))}
      </div>
      <FieldError>{errors.experience}</FieldError>

      <p style={sectionLabelStyle}>Dagen per week</p>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <button
          type="button"
          onClick={() => update({ days_per_week: Math.max(1, form.days_per_week - 1) })}
          style={stepperButtonStyle}
        >
          −
        </button>
        <span style={{ fontSize: 24, fontWeight: 600, minWidth: 32, textAlign: "center" }}>
          {form.days_per_week}
        </span>
        <button
          type="button"
          onClick={() => update({ days_per_week: Math.min(7, form.days_per_week + 1) })}
          style={stepperButtonStyle}
        >
          +
        </button>
      </div>
      <FieldError>{errors.days_per_week}</FieldError>

      <p style={sectionLabelStyle}>Sessieduur</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {DURATIONS.map((min) => (
          <button
            key={min}
            type="button"
            onClick={() => update({ session_minutes: min })}
            style={pillStyle(form.session_minutes === min)}
          >
            {min === 90 ? "90+" : min} min
          </button>
        ))}
      </div>
      <FieldError>{errors.session_minutes}</FieldError>

      <p style={sectionLabelStyle}>Trainingslocatie</p>
      <div style={{ display: "flex", gap: 8 }}>
        {LOCATIONS.map((loc) => (
          <button
            key={loc.value}
            type="button"
            onClick={() => update({ training_location: loc.value })}
            style={{ ...pillStyle(form.training_location === loc.value), flex: 1, borderRadius: 10 }}
          >
            {loc.label}
          </button>
        ))}
      </div>
      <FieldError>{errors.training_location}</FieldError>

      {needsEquipment && (
        <>
          <p style={sectionLabelStyle}>Welke apparatuur heb je?</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {equipmentOptions.map((eq) => {
              const selected = (form.equipment || []).includes(eq.name);
              return (
                <button
                  key={eq.id}
                  type="button"
                  onClick={() => toggleEquipment(eq.name)}
                  style={{ ...pillStyle(selected), textTransform: "capitalize" }}
                >
                  {eq.name}
                </button>
              );
            })}
          </div>
          <FieldError>{errors.equipment}</FieldError>
        </>
      )}

      <FieldError>{errors._general}</FieldError>

      <PrimaryButton onClick={handleSave} disabled={saving}>
        {saving ? "Bezig…" : "Opslaan"}
      </PrimaryButton>

      {showToast && <Toast message="Profiel opgeslagen" onDone={() => setShowToast(false)} />}
    </div>
  );
}
