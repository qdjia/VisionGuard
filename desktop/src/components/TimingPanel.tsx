import type { ReviewTiming } from "../api/types";
import { formatDuration } from "../lib/formatting";

export function TimingPanel({ timing }: { timing: ReviewTiming }) {
  const rows: [string, number][] = [
    ["请求总耗时", timing.request_total_ms], ["排队", timing.queue_wait_ms], ["推理", timing.inference_ms],
    ["检测", timing.detector_ms], ["OCR", timing.ocr_ms], ["文本基线", timing.baseline_ms],
    ["路由", timing.routing_ms], ["VLM", timing.vlm_ms], ["融合", timing.fusion_ms],
  ];
  return <dl className="timing-grid">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{formatDuration(value)}</dd></div>)}</dl>;
}
