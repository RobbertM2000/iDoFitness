import OnboardingShell, { PrimaryButton, OptionCard } from "./OnboardingShell";

export default function GoalScreen({ draft, updateDraft, onNext, onBack }) {
  return (
    <OnboardingShell step={4} onBack={onBack}>
      <h2 style={{ fontSize: 22, fontWeight: 600 }}>Trainingsdoel</h2>
      <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>
        Je kunt dit altijd wijzigen in Instellingen.
      </p>

      <OptionCard
        icon="💪"
        title="Hypertrofie"
        subtitle="Maximale spiergroei. Focus op volume, 6-15 reps."
        selected={draft.global_goal === "hypertrophy"}
        onClick={() => updateDraft({ global_goal: "hypertrophy" })}
      />
      <OptionCard
        icon="🏋️"
        title="Kracht"
        subtitle="Maximale kracht. Focus op 1RM, 1-6 reps."
        selected={draft.global_goal === "strength"}
        onClick={() => updateDraft({ global_goal: "strength" })}
      />

      <PrimaryButton disabled={!draft.global_goal} onClick={onNext}>
        Volgende
      </PrimaryButton>
    </OnboardingShell>
  );
}
