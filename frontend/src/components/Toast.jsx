import { useEffect } from "react";

export default function Toast({ message, onDone, duration = 2500 }) {
  useEffect(() => {
    const timer = setTimeout(onDone, duration);
    return () => clearTimeout(timer);
  }, [onDone, duration]);

  return (
    <div
      role="status"
      style={{
        position: "fixed",
        left: "50%",
        bottom: 88,
        transform: "translateX(-50%)",
        background: "var(--success)",
        color: "#fff",
        padding: "12px 20px",
        borderRadius: 10,
        fontSize: 14,
        fontWeight: 500,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        animation: "toast-in 200ms ease-out",
        zIndex: 20,
      }}
    >
      {message}
    </div>
  );
}
