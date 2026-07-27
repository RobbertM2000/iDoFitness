export function SkeletonBlock({ width = "100%", height = 16, style }) {
  return <div className="skeleton" style={{ width, height, ...style }} />;
}

function SkeletonCard({ height = 90 }) {
  return (
    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <SkeletonBlock width="40%" height={13} style={{ marginBottom: 12 }} />
      <SkeletonBlock height={height} />
    </div>
  );
}

export default function DashboardSkeleton() {
  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "16px 16px 88px" }}>
      <SkeletonBlock width="60%" height={22} style={{ marginBottom: 8 }} />
      <SkeletonBlock width="35%" height={14} style={{ marginBottom: 24 }} />
      <SkeletonCard height={90} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
        <SkeletonCard height={130} />
        <SkeletonCard height={130} />
      </div>
      <SkeletonBlock height={48} style={{ borderRadius: 10, marginBottom: 16 }} />
      <SkeletonCard height={70} />
    </div>
  );
}
