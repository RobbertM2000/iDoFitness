import { useState } from "react";
import OnboardingShell, { PrimaryButton } from "./OnboardingShell";
import FieldError from "../../components/FieldError";
import { ApiError } from "../../context/AuthContext";

const GOAL_LABELS = { hypertrophy: "Hypertrofie", strength: "Kracht" };
const EXPERIENCE_LABELS = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };
const LOCATION_LABELS = { gym: "Sportschool", home: "Thuis", both: "Beide" };

function SummaryRow({ label, value, onEdit }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid var(--text-muted)",
      }}
    >
      <div>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{label}</div>
        <div style={{ fontSize: 15 }}>{value}</div>
      </div>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`${label} wijzigen`}
        style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}
      >
        ✏️
      </button>
    </div>
  );
}

export default function SummaryScreen({ draft, updateDraft, onSubmit, onEditStep, onBack }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!draft.privacy_accepted) return;
    setSubmitting(true);
    setError("");
    try {
      await onSubmit();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Opslaan mislukt — probeer opnieuw"
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <OnboardingShell step={8} onBack={onBack}>
      <h2 style={{ fontSize: 22, fontWeight: 600 }}>Samenvatting</h2>
      <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>
        Klopt dit? Je kunt alles later nog aanpassen in Instellingen.
      </p>

      <SummaryRow label="Naam" value={draft.display_name || "—"} onEdit={() => onEditStep(3)} />
      <SummaryRow
        label="Leeftijd / lengte / gewicht"
        value={`${draft.age} jaar · ${draft.height_cm} cm · ${draft.bodyweight_kg} kg`}
        onEdit={() => onEditStep(3)}
      />
      <SummaryRow label="Trainingsdoel" value={GOAL_LABELS[draft.global_goal]} onEdit={() => onEditStep(4)} />
      <SummaryRow label="Ervaring" value={EXPERIENCE_LABELS[draft.experience]} onEdit={() => onEditStep(5)} />
      <SummaryRow
        label="Beschikbaarheid"
        value={`${draft.days_per_week}x per week · ${draft.session_minutes} min`}
        onEdit={() => onEditStep(6)}
      />
      <SummaryRow
        label="Locatie & apparatuur"
        value={
          draft.training_location === "gym"
            ? LOCATION_LABELS[draft.training_location]
            : `${LOCATION_LABELS[draft.training_location]} · ${(draft.equipment || []).join(", ")}`
        }
        onEdit={() => onEditStep(7)}
      />

      <label style={{ display: "flex", alignItems: "flex-start", gap: 8, marginTop: 20, fontSize: 14 }}>
        <input
          type="checkbox"
          checked={!!draft.privacy_accepted}
          onChange={(e) => updateDraft({ privacy_accepted: e.target.checked })}
          style={{ marginTop: 3 }}
        />
        <span>Ik ga akkoord met het privacybeleid</span>
      </label>
      <FieldError>{error}</FieldError>

      <PrimaryButton disabled={!draft.privacy_accepted || submitting} onClick={handleSubmit}>
        {submitting ? "Bezig…" : "Start met trainen"}
      </PrimaryButton>
    </OnboardingShell>
  );
}
