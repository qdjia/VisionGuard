import type { AdvancedAISnapshot } from "../runtime/types";

export function AdvancedAIStatus({
  snapshot,
  available,
  onRestart,
  onStop,
}: {
  snapshot: AdvancedAISnapshot | null;
  available: boolean;
  onRestart: () => void;
  onStop?: () => void;
}) {
  const state = snapshot?.state;
  const title = state === "loading_model" || state === "starting"
    ? "正在加载"
    : available ? "就绪" : state === "failed" ? "不可用" : state === "installed"
      ? "已安装" : "未安装";
  return <section className="panel" aria-label="Advanced AI status">
    <div className="section-heading"><div><span className="eyebrow">ADVANCED AI</span><h2>{title}</h2></div><span className={available ? "status-dot online" : "status-dot"} aria-hidden="true" /></div>
    {!available && <p>快速审核仍可使用；深度审核需要 Advanced AI Pack。快速模式会在证据不足时按需调用 Advanced AI。</p>}
    {state === "failed" && <div className="warning"><span>Advanced AI 意外停止，Core 不受影响。</span><button type="button" onClick={onRestart}>重启 Advanced AI</button></div>}
    {available && onStop && <button className="button button-secondary" type="button" onClick={onStop}>停止 Advanced AI</button>}
  </section>;
}
