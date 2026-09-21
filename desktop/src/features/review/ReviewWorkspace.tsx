import { useState } from "react";
import type { ReviewResponse, SelectedImage } from "../../api/types";
import { ImagePreview } from "../../components/ImagePreview";
import { AIReviewPanel } from "./AIReviewPanel";
import { DetailsPanel } from "./DetailsPanel";
import { DetectionPanel } from "./DetectionPanel";
import { OCRPanel } from "./OCRPanel";
import { ResultOverview } from "./ResultOverview";

type Tab = "overview" | "detection" | "ocr" | "ai" | "details";
const tabs: [Tab, string][] = [["overview", "总览"], ["detection", "目标检测"], ["ocr", "文字识别"], ["ai", "AI 审核"], ["details", "技术详情"]];

export function ReviewWorkspace({ image, review, showTechnical }: { image: SelectedImage; review: ReviewResponse; showTechnical: boolean }) {
  const [tab, setTab] = useState<Tab>("overview");
  const visibleTabs = showTechnical ? tabs : tabs.filter(([id]) => id !== "details");
  return <div className="workspace"><nav className="tabs" aria-label="审核结果视图">{visibleTabs.map(([id, label]) => <button type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)} key={id}>{label}</button>)}</nav>{tab === "overview" && <div className="overview-grid"><ResultOverview review={review} /><section className="panel"><h3>原始图片</h3><ImagePreview image={image} /></section></div>}{tab === "detection" && <DetectionPanel image={image} details={review.details} />}{tab === "ocr" && <OCRPanel image={image} details={review.details} />}{tab === "ai" && <AIReviewPanel review={review} details={review.details} />}{tab === "details" && <DetailsPanel review={review} />}</div>;
}
