import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";

const MUSCLE_LABELS = {
  chest: "Borst", back: "Rug", quads: "Quads", hamstrings: "Hams",
  glutes: "Glutes", shoulders: "Schouders", biceps: "Biceps",
  triceps: "Triceps", calves: "Kuiten", abs: "Buik",
};

export default function MuscleVolumeBars({ volume }) {
  const entries = Object.entries(volume || {}).filter(([, v]) => v > 0);

  if (entries.length === 0) {
    return (
      <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "36px 0" }}>
        Nog niet genoeg data
      </p>
    );
  }

  const data = entries
    .map(([key, value]) => ({ name: MUSCLE_LABELS[key] || key, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);
  const height = data.length * 26 + 10;

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke="var(--text-muted)" strokeOpacity={0.2} />
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={60}
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            axisLine={false}
            tickLine={false}
          />
          <Bar dataKey="value" fill="var(--primary)" radius={[0, 4, 4, 0]} isAnimationActive={false} barSize={12} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
