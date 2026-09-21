import { useState } from "react";
import type { ReviewDetails, SelectedImage } from "../../api/types";
import { ImagePreview } from "../../components/ImagePreview";
import { formatConfidence } from "../../lib/formatting";

export function DetectionPanel({ image, details }: { image: SelectedImage; details: ReviewDetails | null }) {
  const detections = details?.detections ?? [];
  const [visible, setVisible] = useState(true);
  return <div className="split-panel"><section className="panel"><div className="section-heading"><h3>视觉定位</h3><label className="toggle"><input type="checkbox" checked={visible} onChange={(event) => setVisible(event.target.checked)} />显示检测框</label></div><ImagePreview image={image} detections={visible ? detections : []} overlay="detection" /></section><section className="panel"><div className="section-heading"><h3>检测结果</h3><span>{detections.length} 项</span></div>{detections.length ? <ol className="finding-list">{detections.map((item, index) => <li key={`${item.class_name}-${index}`}><strong>{item.class_name}</strong><span>{formatConfidence(item.confidence)}</span><small>[{item.bbox.x1.toFixed(0)}, {item.bbox.y1.toFixed(0)}] → [{item.bbox.x2.toFixed(0)}, {item.bbox.y2.toFixed(0)}]</small></li>)}</ol> : <div className="empty-small">未检测到风险视觉目标</div>}</section></div>;
}
