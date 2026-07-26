import { useEffect, useRef } from "react";
import { formatMMSS } from "../../hooks/useTimer";

export default function RestTimer({ timer }) {
  const { secondsLeft, isRunning, addSeconds, stop } = timer;
  const dinged = useRef(false);

  useEffect(() => {
    if (!isRunning) {
      dinged.current = false;
      return;
    }
    if (secondsLeft === 0 && !dinged.current) {
      dinged.current = true;
      // Soft "done" flash — a real <audio> ping/vibration is a nice-to-have
      // for a future pass; this keeps the MVP dependency-free.
      if (navigator.vibrate) navigator.vibrate(200);
    }
  }, [secondsLeft, isRunning]);

  if (!isRunning) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 132,
        left: 16,
        right: 16,
        maxWidth: 400,
        margin: "0 auto",
        background: secondsLeft === 0 ? "var(--success)" : "var(--surface)",
        border: "1px solid var(--text-muted)",
        borderRadius: 12,
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        boxShadow: "0 4px 16px rgba(0,0,0,0.15)",
        transition: "background 300ms ease",
        zIndex: 50,
      }}
    >
      <div>
        <div style={{ fontSize: 12, color: secondsLeft === 0 ? "#fff" : "var(--text-muted)" }}>
          Rust
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            color: secondsLeft === 0 ? "#fff" : "var(--text)",
          }}
        >
          {secondsLeft === 0 ? "Klaar!" : formatMMSS(secondsLeft)}
        </div>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <button type="button" onClick={() => addSeconds(-30)} style={pillButtonStyle}>
          −30s
        </button>
        <button type="button" onClick={() => addSeconds(30)} style={pillButtonStyle}>
          +30s
        </button>
        <button type="button" onClick={stop} style={pillButtonStyle}>
          Overslaan
        </button>
      </div>
    </div>
  );
}

const pillButtonStyle = {
  padding: "6px 10px",
  borderRadius: 999,
  border: "1px solid var(--text-muted)",
  background: "var(--bg)",
  color: "var(--text)",
  fontSize: 12,
  cursor: "pointer",
};
