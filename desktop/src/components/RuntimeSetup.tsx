import { useState } from "react";

import type { RuntimeSnapshot } from "../runtime/types";

const labels: Record<string, string> = {
  stopped: "正在准备 VisionGuard",
  starting: "正在检查运行环境",
  validating_models: "正在检查本地 AI 模型",
  launching: "正在启动 AI 引擎",
  waiting_for_live: "正在连接本地 AI 引擎",
  waiting_for_ready: "正在加载 AI 模型",
  unavailable: "AI Runtime 当前不可用",
  failed: "AI Runtime 启动失败",
  stopping: "正在停止 AI Runtime",
};

export function RuntimeSetup({ snapshot, onRestart }: {
  snapshot: RuntimeSnapshot | null;
  onRestart: () => Promise<void>;
}) {
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const state = snapshot?.state ?? "starting";
  const failed = state === "failed" || state === "unavailable";
  const seconds = Math.max(0, Math.floor((snapshot?.elapsed_ms ?? 0) / 1000));
  return <main className="runtime-setup"><section className="runtime-card" aria-live="polite">
    <span className="brand-mark runtime-mark">V</span>
    <span className="eyebrow">LOCAL AI RUNTIME</span>
    <h1>{labels[state] ?? "正在启动 VisionGuard"}</h1>
    {!failed && <><div className="runtime-spinner" aria-hidden="true" /><p>已经过 {seconds} 秒。大型视觉语言模型首次加载可能需要一些时间。</p></>}
    <div className="runtime-components">
      {Object.entries(snapshot?.model_components ?? {}).map(([name, status]) => <span key={name} className={`component-${status}`}>{name}<b>{status === "ready" ? "✓" : status === "missing" ? "缺失" : status}</b></span>)}
    </div>
    {failed && <div className="runtime-failure"><p>{snapshot?.error_message ?? "无法启动本地 AI Runtime。"}</p><code>{snapshot?.error_code ?? "RUNTIME_START_FAILED"}</code><div><button className="button button-primary" onClick={() => void onRestart()}>重新启动 Runtime</button><button className="button button-secondary" onClick={() => setDiagnosticsOpen((value) => !value)}>显示诊断信息</button></div>{diagnosticsOpen && <dl className="runtime-diagnostics"><div><dt>运行模式</dt><dd>{snapshot?.backend_mode}</dd></div><div><dt>Runtime</dt><dd>{snapshot?.runtime_version ?? "未知"}</dd></div><div><dt>模型包</dt><dd>{snapshot?.model_bundle_version ?? "未知"}</dd></div><div><dt>API</dt><dd>{snapshot?.api_version ?? "未知"}</dd></div><div><dt>PID</dt><dd>{snapshot?.pid ?? "—"}</dd></div><div><dt>退出码</dt><dd>{snapshot?.last_exit_code ?? "—"}</dd></div></dl>}</div>}
  </section></main>;
}
