import { useEffect, useState } from "react";

import type {
  ModelBundleInfo,
  ModelInstallStatus,
  RuntimeController,
  RuntimeInstallStatus,
  RuntimePackageInfo,
  RuntimeSnapshot,
} from "../runtime/types";

const labels: Record<string, string> = {
  stopped: "正在准备 VisionGuard",
  starting: "正在检查运行环境",
  checking_hardware: "正在检查 GPU 与磁盘空间",
  validating_models: "正在检查本地 AI 模型",
  launching: "正在启动 AI 引擎",
  waiting_for_live: "正在连接本地 AI 引擎",
  waiting_for_ready: "正在加载 AI 模型",
  unavailable: "AI Runtime 当前不可用",
  failed: "AI Runtime 启动失败",
  stopping: "正在停止 AI Runtime",
};

function readableBytes(value: number): string {
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GiB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  return `${value} B`;
}

function setupError(error: unknown): { code: string; message: string } {
  const fallback = { code: "COMPONENT_INSTALL_FAILED", message: "本地 AI 组件安装失败，请检查安装包后重试。" };
  if (typeof error !== "string") return fallback;
  try {
    const parsed = JSON.parse(error) as { code?: string; message?: string };
    return { code: parsed.code ?? fallback.code, message: parsed.message ?? fallback.message };
  } catch {
    return { ...fallback, message: error || fallback.message };
  }
}

export function RuntimeSetup({ snapshot, controller, onRestart }: {
  snapshot: RuntimeSnapshot | null;
  controller?: RuntimeController;
  onRestart: () => Promise<void>;
}) {
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [source, setSource] = useState<string | null>(null);
  const [bundle, setBundle] = useState<ModelBundleInfo | null>(null);
  const [installStatus, setInstallStatus] = useState<ModelInstallStatus | null>(null);
  const [installError, setInstallError] = useState<{ code: string; message: string } | null>(null);
  const [runtimeSource, setRuntimeSource] = useState<string | null>(null);
  const [runtimePackage, setRuntimePackage] = useState<RuntimePackageInfo | null>(null);
  const [runtimeInstallStatus, setRuntimeInstallStatus] = useState<RuntimeInstallStatus | null>(null);
  const [runtimeInstallError, setRuntimeInstallError] = useState<{ code: string; message: string } | null>(null);
  const state = snapshot?.state ?? "starting";
  const failed = state === "failed" || state === "unavailable";
  const needsModels = snapshot?.error_code === "MODEL_BUNDLE_MISSING" || snapshot?.error_code === "MODEL_BUNDLE_INVALID";
  const needsRuntime = snapshot?.error_code === "RUNTIME_COMPONENT_MISSING";
  const installing = ["inspecting", "installing", "validating"].includes(installStatus?.state ?? "");
  const runtimeInstalling = ["inspecting", "installing", "validating"].includes(runtimeInstallStatus?.state ?? "");
  const seconds = Math.max(0, Math.floor((snapshot?.elapsed_ms ?? 0) / 1000));

  useEffect(() => {
    if (!controller || !installing) return;
    const timer = window.setInterval(() => {
      void controller.modelInstallStatus().then(setInstallStatus).catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [controller, installing]);

  useEffect(() => {
    if (!controller || !runtimeInstalling) return;
    const timer = window.setInterval(() => {
      void controller.runtimeInstallStatus().then(setRuntimeInstallStatus).catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [controller, runtimeInstalling]);

  async function selectBundle(kind: "zip" | "directory") {
    if (!controller) return;
    setInstallError(null);
    setBundle(null);
    const selected = await controller.chooseModelBundle(kind);
    if (!selected) return;
    setSource(selected);
    try {
      const inspected = await controller.inspectModelBundle(selected);
      setBundle(inspected);
    } catch (error) {
      setInstallError(setupError(error));
    }
  }

  async function installBundle() {
    if (!controller || !source || !bundle) return;
    setInstallError(null);
    setInstallStatus({ state: "installing", bundle_version: bundle.bundle_version, error_code: null, error_message: null });
    try {
      await controller.installModelBundle(source);
      setInstallStatus({ state: "ready", bundle_version: bundle.bundle_version, error_code: null, error_message: null });
      await onRestart();
    } catch (error) {
      const parsed = setupError(error);
      setInstallError(parsed);
      setInstallStatus({ state: "failed", bundle_version: bundle.bundle_version, error_code: parsed.code, error_message: parsed.message });
    }
  }

  async function selectRuntime(kind: "zip" | "directory") {
    if (!controller) return;
    setRuntimeInstallError(null);
    setRuntimePackage(null);
    const selected = await controller.chooseRuntimeBundle(kind);
    if (!selected) return;
    setRuntimeSource(selected);
    try {
      setRuntimePackage(await controller.inspectRuntimeBundle(selected));
    } catch (error) {
      setRuntimeInstallError(setupError(error));
    }
  }

  async function installRuntime() {
    if (!controller || !runtimeSource || !runtimePackage) return;
    setRuntimeInstallError(null);
    setRuntimeInstallStatus({ state: "installing", runtime_version: runtimePackage.runtime_version, error_code: null, error_message: null });
    try {
      await controller.installRuntimeBundle(runtimeSource);
      setRuntimeInstallStatus({ state: "ready", runtime_version: runtimePackage.runtime_version, error_code: null, error_message: null });
      await onRestart();
    } catch (error) {
      const parsed = setupError(error);
      setRuntimeInstallError(parsed);
      setRuntimeInstallStatus({ state: "failed", runtime_version: runtimePackage.runtime_version, error_code: parsed.code, error_message: parsed.message });
    }
  }

  return <main className="runtime-setup"><section className="runtime-card" aria-live="polite">
    <span className="brand-mark runtime-mark">V</span>
    <span className="eyebrow">LOCAL AI RUNTIME</span>
    <h1>{labels[state] ?? "正在启动 VisionGuard"}</h1>
    {!failed && <><div className="runtime-spinner" aria-hidden="true" /><p>已经过 {seconds} 秒。大型视觉语言模型首次加载可能需要一些时间。</p></>}
    <div className="runtime-components">
      {Object.entries(snapshot?.model_components ?? {}).map(([name, status]) => <span key={name} className={`component-${status}`}>{name}<b>{status === "ready" ? "✓" : status === "missing" ? "缺失" : status}</b></span>)}
    </div>
    {needsRuntime && controller && <div className="model-setup">
      <h2>安装 GPU Runtime</h2>
      <p>Desktop 安装器保持轻量。请选择独立的 VisionGuard Windows GPU Runtime，组件只会安装到本机用户数据目录。</p>
      <div className="model-actions">
        <button className="button button-primary" disabled={runtimeInstalling} onClick={() => void selectRuntime("zip")}>选择 Runtime ZIP</button>
        <button className="button button-secondary" disabled={runtimeInstalling} onClick={() => void selectRuntime("directory")}>选择已解压 Runtime</button>
      </div>
      {runtimePackage && <dl className="runtime-diagnostics model-summary">
        <div><dt>Runtime</dt><dd>{runtimePackage.runtime_version}</dd></div>
        <div><dt>平台</dt><dd>{runtimePackage.platform} / {runtimePackage.architecture}</dd></div>
        <div><dt>安装大小</dt><dd>{readableBytes(runtimePackage.uncompressed_size_bytes)}</dd></div>
        <div><dt>Desktop 兼容</dt><dd>{runtimePackage.compatible ? "通过" : "不兼容"}</dd></div>
      </dl>}
      {runtimePackage && <button className="button button-primary button-large" disabled={runtimeInstalling || !runtimePackage.compatible} onClick={() => void installRuntime()}>
        {runtimeInstalling ? runtimeInstallStatus?.state === "validating" ? "正在校验 Runtime…" : "正在安装 Runtime…" : "安装 GPU Runtime"}
      </button>}
      {runtimeInstallError && <div className="runtime-failure" role="alert"><p>{runtimeInstallError.message}</p><code>{runtimeInstallError.code}</code></div>}
      <small>Runtime 与模型分开管理。安装失败不会覆盖现有可用 Runtime；应用不会执行远程脚本。</small>
    </div>}
    {needsModels && controller && <div className="model-setup">
      <h2>安装本地 AI 模型</h2>
      <p>VisionGuard 需要独立的离线模型包。模型只会复制到本机用户数据目录，不会上传。</p>
      <div className="model-actions">
        <button className="button button-primary" disabled={installing} onClick={() => void selectBundle("zip")}>选择模型 ZIP</button>
        <button className="button button-secondary" disabled={installing} onClick={() => void selectBundle("directory")}>选择已解压目录</button>
      </div>
      {bundle && <dl className="runtime-diagnostics model-summary">
        <div><dt>模型版本</dt><dd>{bundle.bundle_version}</dd></div>
        <div><dt>来源</dt><dd>{bundle.source_kind === "zip" ? "ZIP 模型包" : "本地目录"}</dd></div>
        <div><dt>安装大小</dt><dd>{readableBytes(bundle.uncompressed_size_bytes)}</dd></div>
        <div><dt>Runtime 兼容</dt><dd>{bundle.runtime_compatible ? "通过" : "不兼容"}</dd></div>
      </dl>}
      {bundle && <button className="button button-primary button-large" disabled={installing || !bundle.runtime_compatible} onClick={() => void installBundle()}>
        {installing ? installStatus?.state === "validating" ? "正在校验 SHA-256…" : "正在安装模型…" : "安装并启动 VisionGuard"}
      </button>}
      {installError && <div className="runtime-failure" role="alert"><p>{installError.message}</p><code>{installError.code}</code></div>}
      <small>安装前会检查磁盘空间、Runtime 兼容性、文件大小与 SHA-256；失败不会覆盖现有可用模型。</small>
    </div>}
    {failed && ((!needsModels && !needsRuntime) || !controller) && <div className="runtime-failure"><p>{snapshot?.error_message ?? "无法启动本地 AI Runtime。"}</p><code>{snapshot?.error_code ?? "RUNTIME_START_FAILED"}</code><div><button className="button button-primary" onClick={() => void onRestart()}>重新启动 Runtime</button><button className="button button-secondary" onClick={() => setDiagnosticsOpen((value) => !value)}>显示诊断信息</button></div>{diagnosticsOpen && <dl className="runtime-diagnostics"><div><dt>运行模式</dt><dd>{snapshot?.backend_mode}</dd></div><div><dt>Runtime</dt><dd>{snapshot?.runtime_version ?? "未知"}</dd></div><div><dt>模型包</dt><dd>{snapshot?.model_bundle_version ?? "未知"}</dd></div><div><dt>API</dt><dd>{snapshot?.api_version ?? "未知"}</dd></div><div><dt>PID</dt><dd>{snapshot?.pid ?? "—"}</dd></div><div><dt>退出码</dt><dd>{snapshot?.last_exit_code ?? "—"}</dd></div></dl>}</div>}
  </section></main>;
}
