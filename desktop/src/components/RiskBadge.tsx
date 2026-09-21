import type { RiskLevel } from "../api/types";

const labels: Record<RiskLevel, string> = { low: "低风险", medium: "中风险", high: "高风险" };

export function RiskBadge({ level }: { level: RiskLevel | null }) {
  if (!level) return <span className="badge badge-neutral">待判断</span>;
  return <span className={`badge badge-${level}`}>{labels[level]}</span>;
}
