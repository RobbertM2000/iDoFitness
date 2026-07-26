const TOTAL_STEPS = 8; // White Paper §4.1: 8 dots total (scherm 1-2 = welcome/account, already done)

export default function OnboardingShell({ step, children, onBack }) {
  return (
    <div style={{ maxWidth: 400, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 24 }}>
        {Array.from({ length: TOTAL_STEPS }, (_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 999,
              background: i < step ? "var(--primary)" : "var(--text-muted)",
              opacity: i < step ? 1 : 0.25,
              transition: "background 200ms ease-out",
            }}
          />
        ))}
      </div>

      {onBack && (
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
            padding: 0,
            marginBottom: 12,
            fontSize: 14,
          }}
        >
          ← Terug
        </button>
      )}

      {children}
    </div>
  );
}

export const inputStyle = {
  display: "block",
  width: "100%",
  height: 44,
  marginTop: 4,
  padding: "0 12px",
  border: "1px solid var(--text-muted)",
  borderRadius: 10,
  background: "var(--surface)",
  color: "var(--text)",
  fontSize: 16,
};

export function PrimaryButton({ children, disabled, ...props }) {
  return (
    <button
      {...props}
      disabled={disabled}
      style={{
        width: "100%",
        height: 48,
        marginTop: 24,
        border: "none",
        borderRadius: 10,
        background: "var(--primary)",
        color: "#fff",
        fontSize: 16,
        fontWeight: 600,
        opacity: disabled ? 0.4 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {children}
    </button>
  );
}

export function OptionCard({ selected, onClick, title, subtitle, icon }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        padding: 16,
        marginBottom: 12,
        borderRadius: 12,
        border: `2px solid ${selected ? "var(--primary)" : "var(--text-muted)"}`,
        background: selected ? "var(--surface)" : "transparent",
        color: "var(--text)",
        cursor: "pointer",
      }}
    >
      <div style={{ fontSize: 16, fontWeight: 600 }}>
        {icon} {title}
      </div>
      {subtitle && (
        <div style={{ fontSize: 14, color: "var(--text-muted)", marginTop: 4 }}>{subtitle}</div>
      )}
    </button>
  );
}
