import { LineChart, Line, ResponsiveContainer } from "recharts";

export default function Sparkline({ data, color = "var(--primary)", height = 40 }) {
  if (!data || data.filter((v) => v != null).length < 2) {
    return (
      <div style={{ height, display: "flex", alignItems: "center", fontSize: 12, color: "var(--text-muted)" }}>
        Nog niet genoeg data
      </div>
    );
  }

  const chartData = data.map((v, i) => ({ i, v }));

  return (
    <div style={{ height, width: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
