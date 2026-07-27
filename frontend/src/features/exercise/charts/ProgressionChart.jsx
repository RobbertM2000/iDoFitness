import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

function formatDateShort(iso) {
  return new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short" });
}

function addDays(iso, days) {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function CustomDot(props) {
  const { cx, cy, payload, dataKey } = props;
  if (cx == null || cy == null || payload[dataKey] == null) return null;
  const isPr = payload.isPr;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={isPr ? 5 : 3}
      fill={isPr ? "var(--success)" : "var(--primary)"}
      stroke={isPr ? "var(--surface)" : "none"}
      strokeWidth={isPr ? 2 : 0}
    />
  );
}

function ChartTooltip({ active, payload, label, unit }) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload.find((p) => p.dataKey === "metric") || payload[0];
  if (point.value == null) return null;
  return (
    <div
      style={{
        background: "var(--surface)", border: "1px solid var(--text-muted)",
        borderRadius: 8, padding: "6px 10px", fontSize: 12,
      }}
    >
      <div style={{ color: "var(--text-muted)" }}>{formatDateShort(label)}</div>
      <div style={{ fontWeight: 600 }}>
        {point.value} {unit}
        {point.payload.isPr && <span style={{ color: "var(--success)" }}> · PR</span>}
      </div>
      {point.payload.reps != null && (
        <div style={{ color: "var(--text-muted)" }}>{point.payload.reps} reps</div>
      )}
    </div>
  );
}

export default function ProgressionChart({ dataPoints, metric, regression, height = 220 }) {
  const key = metric === "weight" ? "weight_kg" : "e1rm_kg";
  const unit = "kg";

  const points = dataPoints
    .filter((p) => p[key] != null)
    .map((p) => ({
      date: p.date,
      metric: p[key],
      reps: p.reps,
      isPr: metric === "weight" ? p.is_pr : p.is_pr && p.e1rm_kg != null,
    }));

  if (points.length === 0) {
    return (
      <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
          {metric === "weight" ? "Nog geen gewicht gelogd" : "Nog geen e1RM-data (reps ≤10 nodig)"}
        </p>
      </div>
    );
  }

  const chartData = [...points];
  // Regression is fitted on e1RM only — only draw the forecast segment
  // when that's the metric currently shown (§5.7).
  if (regression && metric === "e1rm" && chartData.length > 0) {
    const last = chartData[chartData.length - 1];
    chartData[chartData.length - 1] = { ...last, forecast: last.metric };
    chartData.push({
      date: addDays(last.date, 14),
      forecast: regression.forecast_2weeks,
      metric: null,
      isPr: false,
      isForecastPoint: true,
    });
  }

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid stroke="var(--text-muted)" strokeOpacity={0.15} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDateShort}
            tick={{ fontSize: 10, fill: "var(--text-muted)" }}
            axisLine={false}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--text-muted)" }}
            axisLine={false}
            tickLine={false}
            width={36}
            domain={["auto", "auto"]}
          />
          <Tooltip content={<ChartTooltip unit={unit} />} />
          <Line
            type="monotone"
            dataKey="metric"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={<CustomDot />}
            isAnimationActive={false}
            connectNulls
          />
          {regression && metric === "e1rm" && (
            <Line
              type="monotone"
              dataKey="forecast"
              name="verwacht"
              stroke="var(--success)"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              isAnimationActive={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
