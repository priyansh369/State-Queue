export default function StatCard({ label, value, accent, trend }) {
  const trendLabel =
    trend ||
    (accent === "success" ? "Improving" : accent === "danger" ? "Needs attention" : "Stable");

  const trendClass =
    accent === "success" ? "trend-up" : accent === "danger" ? "trend-down" : "trend-stable";
  const accentClass =
    accent === "success" ? "stat-card-success" : accent === "danger" ? "stat-card-danger" : "stat-card-primary";

  return (
    <div className={`stat-card ${accentClass}`}>
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${accent || ""}`}>{value}</div>
      <div className={`stat-trend ${trendClass}`}>{trendLabel}</div>
    </div>
  );
}

