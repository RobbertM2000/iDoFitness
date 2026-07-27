import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from "recharts";

export default function RpeDistributionBars({ distribution }) {
  const entries = Object.entries(distribution || {});
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  if (total === 0) {
    return (
      <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "36px 0" }}>
        Nog niet genoeg data
      </p>
    );
  }

  const data = entries.map(([rpe, count]) => ({ rpe, count }));

  return (
    <div style={{ width: "100%", height: 130 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
          <XAxis
            dataKey="rpe"
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis hide />
          <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
