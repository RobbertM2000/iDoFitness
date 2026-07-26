import OnboardingShell, { PrimaryButton } from "./OnboardingShell";

const DURATIONS = [30, 45, 60, 75, 90];

export default function AvailabilityScreen({ draft, updateDraft, onNext, onBack }) {
  const days = draft.days_per_week || 4;

  return (
    <OnboardingShell step={6} onBack={onBack}>
      <h2 style={{ fontSize: 22, fontWeight: 600 }}>Beschikbaarheid</h2>

      <p style={{ marginTop: 16, marginBottom: 8, fontSize: 14, fontWeight: 500 }}>
        Hoeveel dagen per week train je?
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <button
          type="button"
          onClick={() => updateDraft({ days_per_week: Math.max(1, days - 1) })}
          style={stepperButtonStyle}
        >
          −
        </button>
        <span style={{ fontSize: 24, fontWeight: 600, minWidth: 32, textAlign: "center" }}>
          {days}
        </span>
        <button
          type="button"
          onClick={() => updateDraft({ days_per_week: Math.min(7, days + 1) })}
          style={stepperButtonStyle}
        >
          +
        </button>
      </div>

      <p style={{ marginTop: 24, marginBottom: 8, fontSize: 14, fontWeight: 500 }}>
        Hoe lang duurt een sessie meestal?
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {DURATIONS.map((min) => (
          <button
            key={min}
            type="button"
            onClick={() => updateDraft({ session_minutes: min })}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${draft.session_minutes === min ? "var(--primary)" : "var(--text-muted)"}`,
              background: draft.session_minutes === min ? "var(--primary)" : "transparent",
              color: draft.session_minutes === min ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            {min === 90 ? "90+" : min} min
          </button>
        ))}
      </div>

      <PrimaryButton disabled={!draft.session_minutes} onClick={onNext}>
        Volgende
      </PrimaryButton>
    </OnboardingShell>
  );
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
