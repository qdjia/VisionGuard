import { useEffect, useState } from "react";

import type { VisionGuardBackend } from "./api/types";
import { AnalysisProgress } from "./components/AnalysisProgress";
import { AppShell } from "./components/AppShell";
import { RuntimeSetup } from "./components/RuntimeSetup";
import { ImageDropzone } from "./components/ImageDropzone";
import { ImagePreview } from "./components/ImagePreview";
import { ReviewWorkspace } from "./features/review/ReviewWorkspace";
import { useBackendHealth } from "./hooks/useBackendHealth";
import { useRuntimeStatus } from "./hooks/useRuntimeStatus";
import { useReview } from "./hooks/useReview";
import type { ImageSource } from "./platform/imageSource";
import type { RuntimeController } from "./runtime/types";
import styles from "./styles/App.module.css";

type Theme = "system" | "light" | "dark";

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}><div className="section-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="关闭">关闭</button></div>{children}</section></div>;
}

export function App({ backend, imageSource, runtime }: { backend: VisionGuardBackend; imageSource: ImageSource; runtime?: RuntimeController }) {
  const runtimeStatus = useRuntimeStatus(runtime);
  const { status: health, meta, refresh } = useBackendHealth(backend);
  const defaultMode = (localStorage.getItem("visionguard.defaultMode") as "cascaded" | "full" | null) ?? "cascaded";
  const { state, selectImage, analyze, setMode } = useReview(backend, imageSource, defaultMode);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [showTechnical, setShowTechnical] = useState(() => localStorage.getItem("visionguard.showTechnical") !== "false");
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("visionguard.theme") as Theme | null) ?? "system");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("visionguard.theme", theme);
  }, [theme]);
  useEffect(() => localStorage.setItem("visionguard.showTechnical", String(showTechnical)), [showTechnical]);
  useEffect(() => localStorage.setItem("visionguard.defaultMode", state.mode), [state.mode]);
  useEffect(() => {
    if (meta?.capabilities?.deep_review === false && state.mode === "full") {
      setMode("cascaded");
    }
  }, [meta?.capabilities?.deep_review, setMode, state.mode]);

  const hasImage = "image" in state && Boolean(state.image);
  const busy = state.status === "submitting" || state.status === "analyzing";
  const completed = state.status === "completed" || state.status === "partial";

  if (runtime && runtimeStatus.snapshot?.state !== "ready") {
    return <RuntimeSetup snapshot={runtimeStatus.snapshot} controller={runtime} onRestart={runtimeStatus.restart} />;
  }

  return <AppShell health={health} onSettings={() => setSettingsOpen(true)} onAbout={() => setAboutOpen(true)}><div className={styles.page}>
    <section className={styles.intro}><div><span className="eyebrow">LOCAL-FIRST MULTIMODAL REVIEW</span><h1>让每一次出版审核<br />更清晰、更可追溯</h1><p>融合目标检测、OCR、文本基线与视觉语言模型，用结构化证据辅助内容审核。</p></div><div className="mode-switch" aria-label="审核模式"><button className={state.mode === "cascaded" ? "active" : ""} onClick={() => setMode("cascaded")} disabled={busy}>快速模式<small>智能级联，优先低延迟</small></button><button className={state.mode === "full" ? "active" : ""} onClick={() => setMode("full")} disabled={busy}>深度模式<small>执行完整多模态链路</small></button></div></section>
    {meta?.capabilities && <section className="panel" aria-label="Advanced AI status"><div className="section-heading"><div><span className="eyebrow">ADVANCED AI</span><h2>{meta.capabilities.vlm_available ? "已安装" : "未安装"}</h2></div><span className={meta.capabilities.vlm_available ? "status-dot online" : "status-dot"} aria-hidden="true" /></div>{!meta.capabilities.vlm_available && <p>快速审核可正常使用；深度审核需要安装 Advanced AI Pack。</p>}</section>}
    {!hasImage && <ImageDropzone onSelect={() => void selectImage()} />}
    {hasImage && !completed && <div className="selection-grid"><section className="panel"><ImagePreview image={state.image!} /></section><section className="panel action-card"><span className="eyebrow">READY TO REVIEW</span><h2>{state.image!.name}</h2><p>{state.mode === "cascaded" ? "系统将先执行快速审核，仅在证据不足或冲突时调用 VLM。" : "系统将执行包括 VLM 在内的完整分析链路。"}</p>{busy ? <AnalysisProgress startedAt={state.startedAt} /> : <><button className="button button-primary button-large" type="button" onClick={() => void analyze()} disabled={health !== "ready"}>开始审核</button><button className="button button-secondary" type="button" onClick={() => void selectImage()}>更换图片</button>{health !== "ready" && <div className="warning"><span>AI Runtime 尚未就绪。</span><button type="button" onClick={() => void refresh()}>重新检测</button></div>}</>}</section></div>}
    {completed && <><div className="workspace-actions"><button className="button button-secondary" onClick={() => void selectImage()}>审核另一张图片</button></div><ReviewWorkspace image={state.image} review={state.result} showTechnical={showTechnical} /></>}
    {state.status === "failed" && <section className="error-panel" role="alert"><span>分析未完成</span><h2>{state.error.message}</h2>{state.error.requestId && <p className="mono">Request ID: {state.error.requestId}</p>}<div><button className="button button-primary" onClick={() => void analyze()} disabled={!state.image}>重试</button><button className="button button-secondary" onClick={() => void selectImage()}>选择其他图片</button></div></section>}
  </div>{settingsOpen && <Modal title="偏好设置" onClose={() => setSettingsOpen(false)}><div className="settings-list"><label><span><strong>默认审核模式</strong><small>新会话默认采用的推理路径</small></span><select value={state.mode} onChange={(event) => setMode(event.target.value as "cascaded" | "full")}><option value="cascaded">快速模式</option><option value="full">深度模式</option></select></label><label><span><strong>主题</strong><small>跟随系统或固定外观</small></span><select value={theme} onChange={(event) => setTheme(event.target.value as Theme)}><option value="system">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></label><label><span><strong>技术详情</strong><small>显示模型版本、路由、融合证据与耗时</small></span><input type="checkbox" checked={showTechnical} onChange={(event) => setShowTechnical(event.target.checked)} /></label></div></Modal>}{aboutOpen && <Modal title="关于 VisionGuard" onClose={() => setAboutOpen(false)}><p>面向出版内容审核场景的本地优先多模态智能审校工作台。</p><dl className="kv"><div><dt>桌面端</dt><dd>0.1.0</dd></div><div><dt>服务端</dt><dd>{meta?.service_version ?? "未连接"}</dd></div><div><dt>API</dt><dd>{meta?.api_version ?? "—"}</dd></div><div><dt>Pipeline</dt><dd>{meta?.pipeline_versions.full ?? meta?.pipeline_versions.cascaded ?? "—"}</dd></div><div><dt>许可证</dt><dd>MIT</dd></div></dl><p><a href="https://github.com/qdjia/VisionGuard" target="_blank" rel="noreferrer">GitHub 项目主页</a></p></Modal>}</AppShell>;
}
