import SetRow from "./SetRow";

function formatPrevious(previousSets) {
  if (!previousSets || previousSets.length === 0) return null;
  const reps = previousSets.map((s) => s.reps).join(",");
  const weight = previousSets[0].weight_kg;
  const rpes = previousSets.map((s) => s.rpe).filter((r) => r != null);
  const avgRpe = rpes.length ? (rpes.reduce((a, b) => a + b, 0) / rpes.length).toFixed(1) : null;
  return `Vorige: ${weight} kg × ${reps}${avgRpe ? ` @ RPE ${avgRpe}` : ""}`;
}

export default function ExerciseCard({ item, onUpdateSet, onAddSet, onRemoveSet, onCompleteSet, onRemoveExercise }) {
  const previousLine = formatPrevious(item.previousSets);

  return (
    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3 style={{ fontSize: 17, fontWeight: 600, margin: 0 }}>{item.exercise.name}</h3>
          {previousLine && (
            <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "2px 0 0" }}>{previousLine}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onRemoveExercise}
          aria-label="Oefening verwijderen"
          style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 14 }}
        >
          Verwijder
        </button>
      </div>

      <div style={{ marginTop: 12 }}>
        {item.sets.map((set, i) => (
          <SetRow
            key={set.tempId}
            set={set}
            index={i}
            onChange={(patch) => onUpdateSet(set.tempId, patch)}
            onComplete={() => onCompleteSet(set.tempId)}
            onRemove={() => onRemoveSet(set.tempId)}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={onAddSet}
        style={{
          marginTop: 8, padding: "8px 12px", borderRadius: 8, border: "1px dashed var(--text-muted)",
          background: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 14,
        }}
      >
        + Set
      </button>
    </div>
  );
}
