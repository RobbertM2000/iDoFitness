import OnboardingShell, { PrimaryButton } from "./OnboardingShell";

const OPTIONS = [
  { value: "beginner", label: "Beginner", sub: "<1 jaar" },
  { value: "intermediate", label: "Intermediate", sub: "1-3 jaar" },
  { value: "advanced", label: "Advanced", sub: "3+ jaar" },
];

export default function ExperienceScreen({ draft, updateDraft, onNext, onBack }) {
  return (
    <OnboardingShell step={5} onBack={onBack}>
      <h2 style={{ fontSize: 22, fontWeight: 600 }}>Trainingservaring</h2>
      <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>
        Dit bepaalt hoe agressief we je progressie opbouwen.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => updateDraft({ experience: opt.value })}
            style={{
              padding: 16,
              borderRadius: 12,
              border: `2px solid ${draft.experience === opt.value ? "var(--primary)" : "var(--text-muted)"}`,
              background: draft.experience === opt.value ? "var(--surface)" : "transparent",
              color: "var(--text)",
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <div style={{ fontWeight: 600 }}>{opt.label}</div>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{opt.sub}</div>
          </button>
        ))}
      </div>

      <PrimaryButton disabled={!draft.experience} onClick={onNext}>
        Volgende
      </PrimaryButton>
    </OnboardingShell>
  );
}
