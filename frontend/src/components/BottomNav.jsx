const TABS = [
  { key: "home", icon: "🏠", label: "Home" },
  { key: "log", icon: "✍️", label: "Log" },
  { key: "suggestion", icon: "⚡", label: "Suggestie" },
  { key: "history", icon: "📜", label: "Historie" },
  { key: "settings", icon: "⚙️", label: "Instellingen" },
];

export default function BottomNav({ active, onChange }) {
  return (
    <nav
      style={{
        position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 10,
        display: "flex", justifyContent: "space-around",
        background: "var(--surface)", borderTop: "1px solid var(--text-muted)",
        padding: "8px 0",
      }}
    >
      {TABS.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
            background: "none", border: "none", cursor: "pointer",
            color: active === tab.key ? "var(--primary)" : "var(--text-muted)",
            fontSize: 11, padding: "4px 12px",
          }}
        >
          <span style={{ fontSize: 20 }}>{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
