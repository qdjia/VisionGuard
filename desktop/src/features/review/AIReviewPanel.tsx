import type { ReviewDetails, ReviewResponse } from "../../api/types";
import { formatConfidence } from "../../lib/formatting";

export function AIReviewPanel({ review, details }: { review: ReviewResponse; details: ReviewDetails | null }) {
  if (review.modules.vlm === "skipped") return <section className="panel empty-panel"><span className="route-mark">FAST</span><h3>本次未调用视觉语言模型</h3><p>级联路由已在快速阶段获得清晰结论，从而减少延迟与 GPU 开销。</p></section>;
  if (review.modules.vlm === "failed") return <section className="panel"><div className="warning">视觉语言模型未完成，请结合其他模块结果人工复核。</div></section>;
  return <section className="panel"><div className="section-heading"><div><span className="eyebrow">Vision-Language Model</span><h3>语义审核</h3></div><strong>{formatConfidence(details?.vlm_confidence)}</strong></div><p className="reason">{details?.vlm_reason || "模型未提供额外说明。"}</p><div className="chip-row">{details?.vlm_categories.map((item) => <span className="chip" key={item}>{item}</span>)}</div><h4>证据</h4>{details?.vlm_evidence.length ? <ul className="evidence-list">{details.vlm_evidence.map((item, index) => <li key={`${item.type}-${index}`}><strong>{item.type}</strong><p>{item.description}</p>{item.text && <blockquote>{item.text}</blockquote>}</li>)}</ul> : <div className="empty-small">无结构化 VLM 证据</div>}</section>;
}
