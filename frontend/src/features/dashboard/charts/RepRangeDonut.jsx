import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

const COLORS = ["var(--primary)", "var(--success)", "var(--warning)"];
const LABELS = { "6-10": "6-10 reps", "10-15": "10-15 reps", "15+": "15+ reps" };

export default function RepRangeDonut({ distribution }) {
  const entries = Object.entries(distribution || {}).filter(([, v]) => v > 0);

  if (entries.length === 0) {
    return <EmptyState />;
  }

  const data = entries.map(([key, value]) => ({ name: LABELS[key] || key, value, key }));

  return (
    <div>
      <div style={{ height: 130 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={36}
              outerRadius={58}
              paddingAngle={2}
              isAnimationActive={false}
            >
              {data.map((entry, i) => (
                <Cell key={entry.key} fill={COLORS[i % COLORS.length]} stroke="none" />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
        {data.map((entry, i) => (
          <div key={entry.key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span
              style={{
                width: 8, height: 8, borderRadius: "50%",
                background: COLORS[i % COLORS.length], flexShrink: 0,
              }}
            />
            <span style={{ color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {entry.name}
            </span>
            <span style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums", fontWeight: 600, flexShrink: 0 }}>
              {entry.value}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "36px 0" }}>
      Nog niet genoeg data
    </p>
  );
}
