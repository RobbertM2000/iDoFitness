import { DRAFT_STALE_MS } from "../../context/WorkoutContext";

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleString("nl-NL", {
    day: "numeric", month: "long", hour: "2-digit", minute: "2-digit",
  });
}

function countCompletedSets(draft) {
  return draft.exercises.reduce((sum, ex) => sum + ex.sets.filter((s) => s.completed).length, 0);
}

// White Paper §7.2 (resume prompt) / §16 edge case #2 (>12h stale drafts).
// Rendered by Logger only — switching to another bottom-nav tab simply
// unmounts this dialog along with Logger, it doesn't discard anything,
// since the underlying draft the dialog describes lives in WorkoutContext.
// The backdrop deliberately stops above BottomNav (60px, same convention
// Logger's own finish-button bar uses) rather than using inset:0, so the
// dialog can never trap the user on the Log tab — they can still switch
// to Dashboard/Suggestion/etc. without resolving it first (White Paper §7.2).
export default function ResumeDraftDialog({ draft, saving, error, onResume, onDiscard, onSaveIncomplete }) {
  const isStale = Date.now() - Date.parse(draft.started_at) > DRAFT_STALE_MS;
  const completedCount = countCompletedSets(draft);

  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 60,
        background: "rgba(0,0,0,0.5)", zIndex: 30,
        display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
      }}
    >
      <div style={{ background: "var(--surface)", borderRadius: 12, padding: 20, maxWidth: 340, width: "100%" }}>
        {isStale ? (
          <>
            <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 600 }}>
              Niet-afgeronde workout gevonden
            </h3>
            <p style={{ margin: "0 0 16px", fontSize: 14, color: "var(--text-muted)" }}>
              Je workout van {formatDateTime(draft.started_at)} is niet afgerond
              {completedCount > 0 && ` (${completedCount} ${completedCount === 1 ? "set" : "sets"} gelogd)`}.
              Wil je deze opslaan als onvolledige workout, of verwijderen?
            </p>
            {error && <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--danger)" }}>{error}</p>}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" onClick={onDiscard} disabled={saving} style={secondaryBtnStyle}>
                Verwijderen
              </button>
              <button type="button" onClick={onSaveIncomplete} disabled={saving} style={primaryBtnStyle}>
                {saving ? "Bezig…" : "Opslaan als onvolledig"}
              </button>
            </div>
          </>
        ) : (
          <>
            <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 600 }}>
              Workout hervatten?
            </h3>
            <p style={{ margin: "0 0 16px", fontSize: 14, color: "var(--text-muted)" }}>
              Doorgaan met je workout van {formatTime(draft.started_at)}?
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" onClick={onDiscard} style={secondaryBtnStyle}>
                Verwijderen
              </button>
              <button type="button" onClick={onResume} style={primaryBtnStyle}>
                Doorgaan
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const secondaryBtnStyle = {
  flex: 1, height: 44, borderRadius: 10, border: "1px solid var(--text-muted)",
  background: "none", color: "var(--text)", fontSize: 14, fontWeight: 600, cursor: "pointer",
};

const primaryBtnStyle = {
  flex: 1, height: 44, borderRadius: 10, border: "none",
  background: "var(--primary)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer",
};
