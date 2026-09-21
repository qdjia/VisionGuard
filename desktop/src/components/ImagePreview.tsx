import type { OCRBlockDetail, SelectedImage, DetectionDetail } from "../api/types";
import { formatFileSize } from "../lib/formatting";

export type OverlayKind = "none" | "detection" | "ocr";

export function ImagePreview({ image, detections = [], ocrBlocks = [], overlay = "none" }: { image: SelectedImage; detections?: DetectionDetail[]; ocrBlocks?: OCRBlockDetail[]; overlay?: OverlayKind }) {
  return <div><div className="image-stage"><img src={image.previewUrl} alt={`待审核图片：${image.name}`} />{overlay !== "none" && <svg className="overlay" viewBox={`0 0 ${image.width} ${image.height}`} aria-label={overlay === "detection" ? "目标检测标注" : "OCR 文本标注"}>
    {overlay === "detection" && detections.map((item, index) => <g key={`${item.class_name}-${index}`}><rect className="detection-box" x={item.bbox.x1} y={item.bbox.y1} width={item.bbox.x2 - item.bbox.x1} height={item.bbox.y2 - item.bbox.y1} /><text className="overlay-label" x={item.bbox.x1 + 4} y={Math.max(14, item.bbox.y1 + 15)}>{item.class_name} {(item.confidence * 100).toFixed(0)}%</text></g>)}
    {overlay === "ocr" && ocrBlocks.map((item, index) => <polygon className="ocr-box" key={`${item.text}-${index}`} points={item.polygon.map(([x, y]) => `${x},${y}`).join(" ")} />)}
  </svg>}</div><div className="file-meta"><strong>{image.name}</strong><span>{image.width} × {image.height}</span><span>{formatFileSize(image.size)}</span></div></div>;
}
