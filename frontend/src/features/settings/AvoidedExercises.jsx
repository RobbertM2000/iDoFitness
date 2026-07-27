import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import ExerciseSearch from "../exercise/ExerciseSearch";
import Spinner from "../../components/Spinner";
import Toast from "../../components/Toast";

const MUSCLE_LABELS = {
  chest: "Borst", back: "Rug", quads: "Quads", hamstrings: "Hamstrings",
  glutes: "Glutes", shoulders: "Schouders", biceps: "Biceps",
  triceps: "Triceps", calves: "Kuiten", abs: "Buik",
};

const REASON_MAX = 120;

function MuscleChip({ muscle }) {
  if (!muscle) return null;
  return (
    <span
      style={{
        display: "inline-block", fontSize: 11, fontWeight: 500,
        padding: "2px 8px", borderRadius: 999,
        background: "var(--bg)", color: "var(--text-muted)",
        textTransform: "capitalize",
      }}
    >
      {MUSCLE_LABELS[muscle] || muscle}
    </span>
  );
}

export default function AvoidedExercises() {
  const [items, setItems] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [showPicker, setShowPicker] = useState(false);
  const [pending, setPending] = useState(null); // { id, name, muscle } awaiting a reason
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  const load = () => {
    api.get("/exercises/avoided")
      .then((data) => setItems(data.avoided_exercises))
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Vermijdlijst laden mislukt"));
  };

  useEffect(load, []);

  const handlePick = async (exerciseId) => {
    setShowPicker(false);
    try {
      const ex = await api.get(`/exercises/${exerciseId}`);
      setPending({ id: ex.id, name: ex.name, muscle: ex.muscle });
      setReason("");
    } catch (err) {
      setToastMessage(err instanceof ApiError ? err.message : "Oefening laden mislukt");
    }
  };

  const confirmAdd = async () => {
    if (!pending) return;
    setSaving(true);
    try {
      await api.post(`/exercises/${pending.id}/avoid`, { reason: reason.trim() });
      setPending(null);
      setReason("");
      setToastMessage("Oefening toegevoegd aan vermijdlijst");
      load();
    } catch (err) {
      setToastMessage(err instanceof ApiError ? err.message : "Toevoegen mislukt");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (exerciseId) => {
    const previous = items;
    setItems((list) => list.filter((it) => it.exercise_id !== exerciseId));
    try {
      await api.delete(`/exercises/${exerciseId}/avoid`);
      setToastMessage("Oefening verwijderd van vermijdlijst");
    } catch (err) {
      setItems(previous);
      setToastMessage(err instanceof ApiError ? err.message : "Verwijderen mislukt");
    }
  };

  return (
    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginTop: 24 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 4px" }}>
        Blessures &amp; te vermijden oefeningen
      </h3>
      <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "0 0 12px" }}>
        Oefeningen op deze lijst worden nooit voorgesteld in je workout van vandaag.
      </p>

      {loadError && (
        <p style={{ color: "var(--danger)", fontSize: 13, marginBottom: 12 }}>{loadError}</p>
      )}

      {items === null && !loadError && (
        <div style={{ textAlign: "center", padding: "12px 0" }}>
          <Spinner />
        </div>
      )}

      {items !== null && items.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "0 0 12px" }}>
          Je hebt geen oefeningen op je vermijdlijst. Voeg een oefening toe als je door
          een blessure of voorkeur iets wilt overslaan.
        </p>
      )}

      {items !== null && items.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
          {items.map((it) => (
            <div
              key={it.exercise_id}
              style={{
                display: "flex", alignItems: "flex-start", justifyContent: "space-between",
                gap: 8, padding: "10px 0", borderBottom: "1px solid var(--bg)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 500, fontSize: 14 }}>{it.name}</span>
                  <MuscleChip muscle={it.muscle} />
                </div>
                {it.reason && (
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-muted)" }}>
                    {it.reason}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleRemove(it.exercise_id)}
                aria-label={`${it.name} verwijderen van vermijdlijst`}
                style={{
                  background: "none", border: "none", color: "var(--text-muted)",
                  cursor: "pointer", fontSize: 18, lineHeight: 1, padding: 2, flexShrink: 0,
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {pending ? (
        <div style={{ background: "var(--bg)", borderRadius: 10, padding: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span style={{ fontWeight: 500, fontSize: 14 }}>{pending.name}</span>
            <MuscleChip muscle={pending.muscle} />
          </div>
          <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
            Reden (optioneel)
          </label>
          <textarea
            value={reason}
            maxLength={REASON_MAX}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Bijv. schouderblessure"
            rows={2}
            style={{
              width: "100%", padding: 8, borderRadius: 8, border: "1px solid var(--text-muted)",
              background: "var(--surface)", color: "var(--text)", fontSize: 14, resize: "none",
              boxSizing: "border-box",
            }}
          />
          <div style={{ textAlign: "right", fontSize: 11, color: "var(--text-muted)", margin: "2px 0 10px" }}>
            {reason.length}/{REASON_MAX}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => setPending(null)}
              disabled={saving}
              style={{
                flex: 1, padding: "10px 0", borderRadius: 10, border: "1px solid var(--text-muted)",
                background: "none", color: "var(--text)", fontSize: 14, cursor: "pointer",
              }}
            >
              Annuleren
            </button>
            <button
              type="button"
              onClick={confirmAdd}
              disabled={saving}
              style={{
                flex: 1, padding: "10px 0", borderRadius: 10, border: "none",
                background: "var(--primary)", color: "#fff", fontSize: 14, fontWeight: 600,
                cursor: saving ? "default" : "pointer", opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? "Bezig…" : "Toevoegen"}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowPicker(true)}
          style={{
            width: "100%", padding: "10px 0", borderRadius: 10,
            border: "1px dashed var(--text-muted)", background: "none",
            color: "var(--primary)", fontSize: 14, fontWeight: 600, cursor: "pointer",
          }}
        >
          + Oefening toevoegen
        </button>
      )}

      {showPicker && (
        <ExerciseSearch onSelect={handlePick} onClose={() => setShowPicker(false)} />
      )}

      {toastMessage && <Toast message={toastMessage} onDone={() => setToastMessage("")} />}
    </div>
  );
}
