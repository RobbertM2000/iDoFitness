import { useEffect, useState } from "react";
import OnboardingShell, { PrimaryButton } from "./OnboardingShell";
import { api } from "../../api/client";

const LOCATIONS = [
  { value: "gym", label: "Sportschool" },
  { value: "home", label: "Thuis" },
  { value: "both", label: "Beide" },
];

export default function EquipmentScreen({ draft, updateDraft, onNext, onBack }) {
  const [available, setAvailable] = useState([]);
  const needsEquipment = draft.training_location === "home" || draft.training_location === "both";

  useEffect(() => {
    if (needsEquipment && available.length === 0) {
      api.get("/equipment").then((data) => setAvailable(data.equipment));
    }
  }, [needsEquipment, available.length]);

  const toggleEquipment = (name) => {
    const current = draft.equipment || [];
    const next = current.includes(name)
      ? current.filter((n) => n !== name)
      : [...current, name];
    updateDraft({ equipment: next });
  };

  const canProceed =
    draft.training_location === "gym" ||
    (needsEquipment && (draft.equipment || []).length > 0);

  return (
    <OnboardingShell step={7} onBack={onBack}>
      <h2 style={{ fontSize: 22, fontWeight: 600 }}>Apparatuur & locatie</h2>

      <p style={{ marginTop: 16, marginBottom: 8, fontSize: 14, fontWeight: 500 }}>
        Waar train je?
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        {LOCATIONS.map((loc) => (
          <button
            key={loc.value}
            type="button"
            onClick={() => updateDraft({ training_location: loc.value })}
            style={{
              flex: 1,
              padding: "10px 8px",
              borderRadius: 10,
              border: `1px solid ${draft.training_location === loc.value ? "var(--primary)" : "var(--text-muted)"}`,
              background: draft.training_location === loc.value ? "var(--primary)" : "transparent",
              color: draft.training_location === loc.value ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            {loc.label}
          </button>
        ))}
      </div>

      {needsEquipment && (
        <>
          <p style={{ marginTop: 24, marginBottom: 8, fontSize: 14, fontWeight: 500 }}>
            Welke apparatuur heb je?
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {available.map((eq) => {
              const selected = (draft.equipment || []).includes(eq.name);
              return (
                <button
                  key={eq.id}
                  type="button"
                  onClick={() => toggleEquipment(eq.name)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 999,
                    border: `1px solid ${selected ? "var(--primary)" : "var(--text-muted)"}`,
                    background: selected ? "var(--primary)" : "transparent",
                    color: selected ? "#fff" : "var(--text)",
                    cursor: "pointer",
                    fontSize: 14,
                    textTransform: "capitalize",
                  }}
                >
                  {eq.name}
                </button>
              );
            })}
          </div>
        </>
      )}

      <PrimaryButton disabled={!draft.training_location || !canProceed} onClick={onNext}>
        Volgende
      </PrimaryButton>
    </OnboardingShell>
  );
}
