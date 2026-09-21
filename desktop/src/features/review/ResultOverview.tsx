import type { ReviewResponse } from "../../api/types";
import { RiskBadge } from "../../components/RiskBadge";
import { formatConfidence, formatDuration, formatRiskScore } from "../../lib/formatting";

export function ResultOverview({ review }: { review: ReviewResponse }) {
  const { result } = review;
  return <section className="panel result-hero"><div className="result-title"><div><span className="eyebrow">审核结论</span><h2>{result.requires_manual_review ? "建议人工复核" : "自动审核已完成"}</h2></div><RiskBadge level={result.risk_level} /></div>{review.status === "partial" && <div className="warning" role="alert">部分分析模块未能完成，当前结论可能不完整，请人工复核。</div>}<p className="reason">{result.reason}</p><div className="metrics"><div><span>风险评分</span><strong>{formatRiskScore(result.risk_score)}</strong></div><div><span>总耗时</span><strong>{formatDuration(review.timing.request_total_ms)}</strong></div><div><span>决策来源</span><strong>{result.decision_source}</strong></div></div><p className="disclaimer">风险评分仅表示模型证据强度，不等同于违规概率；最终出版决定应结合审核规范与人工判断。</p><div className="chip-row">{result.categories.length ? result.categories.map((category) => <span className="chip" key={category.name}>{category.name} · {formatConfidence(category.score)}</span>) : <span className="muted">未发现明确风险类别</span>}</div></section>;
}
