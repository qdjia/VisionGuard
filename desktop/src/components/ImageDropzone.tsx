export function ImageDropzone({ onSelect, disabled = false }: { onSelect: () => void; disabled?: boolean }) {
  return <section className="dropzone" aria-label="图片选择区"><div className="drop-icon" aria-hidden="true">＋</div><h2>拖入出版图片开始审核</h2><p>支持 PNG、JPEG、WebP，单张不超过 15 MB</p><button className="button button-primary" type="button" onClick={onSelect} disabled={disabled}>选择图片</button><small>图片仅发送给本机 VisionGuard AI Runtime</small></section>;
}
