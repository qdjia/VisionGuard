import { useState } from "react";
import type { ReviewDetails, SelectedImage } from "../../api/types";
import { ImagePreview } from "../../components/ImagePreview";
import { formatConfidence } from "../../lib/formatting";

export function OCRPanel({ image, details }: { image: SelectedImage; details: ReviewDetails | null }) {
  const blocks = details?.ocr_blocks ?? [];
  const [visible, setVisible] = useState(true);
  const copy = () => void navigator.clipboard.writeText(details?.ocr_full_text ?? "");
  return <div className="split-panel"><section className="panel"><div className="section-heading"><h3>文字区域</h3><label className="toggle"><input type="checkbox" checked={visible} onChange={(event) => setVisible(event.target.checked)} />显示 OCR 区域</label></div><ImagePreview image={image} ocrBlocks={visible ? blocks : []} overlay="ocr" /></section><section className="panel"><div className="section-heading"><div><h3>识别文本</h3><span>{blocks.length} 个文本块 · 平均置信度 {formatConfidence(details?.mean_ocr_confidence)}</span></div><button className="button button-secondary" type="button" onClick={copy} disabled={!details?.ocr_full_text}>复制文本</button></div><div className="ocr-text" tabIndex={0}>{details?.ocr_full_text || "未识别到文字"}</div>{blocks.length > 0 && <ol className="ocr-blocks">{blocks.map((block, index) => <li key={`${block.text}-${index}`}><span>{block.text}</span><small>{formatConfidence(block.confidence)}</small></li>)}</ol>}</section></div>;
}
