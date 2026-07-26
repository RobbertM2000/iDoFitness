import { useState } from "react";
import OnboardingShell, { inputStyle, PrimaryButton } from "./OnboardingShell";
import FieldError from "../../components/FieldError";

const SEX_OPTIONS = [
  { value: "man", label: "Man" },
  { value: "vrouw", label: "Vrouw" },
  { value: "anders", label: "Anders" },
  { value: "zeg_ik_liever_niet", label: "Zeg ik liever niet" },
];

export default function BasicInfoScreen({ draft, updateDraft, onNext, onBack }) {
  const [errors, setErrors] = useState({});

  const handleNext = () => {
    const next = {};
    const age = Number(draft.age);
    if (!age || age < 16 || age > 100) {
      next.age = age && age < 16
        ? "iDoFitness geeft trainingsadvies voor 16+"
        : "Vul een geldige leeftijd in (16-100)";
    }
    const height = Number(draft.height_cm);
    if (!height || height < 120 || height > 230) {
      next.height_cm = "Lengte moet tussen 120 en 230 cm liggen";
    }
    const weight = Number(draft.bodyweight_kg);
    if (!weight || weight < 30 || weight > 300) {
      next.bodyweight_kg = "Gewicht moet tussen 30 en 300 kg liggen";
    }
    if (!draft.sex) {
      next.sex = "Maak een keuze";
    }
    if (Object.keys(next).length) {
      setErrors(next);
      return;
    }
    onNext();
  };

  return (
    <OnboardingShell step={3} onBack={onBack}>
      <h2 style={{ fontSize: 22, fontWeight: 600 }}>Basisgegevens</h2>
      <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>
        Dit helpt ons je aanbevelingen persoonlijk te maken.
      </p>

      <label>
        Naam (optioneel)
        <input
          value={draft.display_name}
          onChange={(e) => updateDraft({ display_name: e.target.value })}
          style={inputStyle}
        />
      </label>

      <label style={{ display: "block", marginTop: 16 }}>
        Leeftijd
        <input
          type="number"
          value={draft.age}
          onChange={(e) => updateDraft({ age: e.target.value })}
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.age}</FieldError>

      <label style={{ display: "block", marginTop: 16 }}>
        Lengte (cm)
        <input
          type="number"
          value={draft.height_cm}
          onChange={(e) => updateDraft({ height_cm: e.target.value })}
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.height_cm}</FieldError>

      <label style={{ display: "block", marginTop: 16 }}>
        Gewicht (kg)
        <input
          type="number"
          value={draft.bodyweight_kg}
          onChange={(e) => updateDraft({ bodyweight_kg: e.target.value })}
          style={inputStyle}
        />
      </label>
      <FieldError>{errors.bodyweight_kg}</FieldError>

      <p style={{ marginTop: 16, marginBottom: 8, fontSize: 14, fontWeight: 500 }}>Geslacht</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {SEX_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => updateDraft({ sex: opt.value })}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${draft.sex === opt.value ? "var(--primary)" : "var(--text-muted)"}`,
              background: draft.sex === opt.value ? "var(--primary)" : "transparent",
              color: draft.sex === opt.value ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <FieldError>{errors.sex}</FieldError>

      <PrimaryButton onClick={handleNext}>Volgende</PrimaryButton>
    </OnboardingShell>
  );
}
