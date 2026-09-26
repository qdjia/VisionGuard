import type { AdvancedAIInstallStatus, AdvancedAIPackageInfo, AdvancedAISnapshot } from "../runtime/types";

const ACTIVE_STATES = new Set([
  "Preparing", "DownloadingRuntime", "CreatingEnvironment", "InstallingDependencies",
  "DownloadingModel", "Validating", "Updating", "Removing", "validating", "installing", "activating",
]);

function bytes(value: number) {
  return `${(value / 1024 ** 3).toFixed(2)} GiB`;
}

const STEP_LABELS: Record<string, string> = {
  Preparing: "准备安装",
  DownloadingRuntime: "下载受管 Python",
  CreatingEnvironment: "创建隔离环境",
  InstallingDependencies: "安装固定版本依赖",
  DownloadingModel: "下载固定版本模型",
  Validating: "验证本地运行环境",
  Updating: "更新 Advanced AI",
  Removing: "移除 Advanced AI",
};

export function AdvancedAIStatus({
  snapshot, available, installStatus = null, packageInfo = null, operationError = null,
  onRestart, onStop, onSelectPackage, onInstall, onCancelInstall, onUninstall, onRollback,
}: {
  snapshot: AdvancedAISnapshot | null;
  available: boolean;
  installStatus?: AdvancedAIInstallStatus | null;
  packageInfo?: AdvancedAIPackageInfo | null;
  operationError?: string | null;
  onRestart: () => void;
  onStop?: () => void;
  onSelectPackage?: () => void;
  onInstall?: () => void;
  onCancelInstall?: () => void;
  onUninstall?: () => void;
  onRollback?: () => void;
}) {
  const state = snapshot?.state;
  const installing = ACTIVE_STATES.has(installStatus?.state ?? "");
  const determinate = Boolean(installStatus?.bytes_total);
  const progress = determinate
    ? Math.min(100, Math.round((installStatus?.bytes_completed ?? 0) * 100 / (installStatus?.bytes_total ?? 1)))
    : 0;
  const title = installing ? "正在安装 Advanced AI"
    : state === "loading_model" || state === "starting" ? "正在加载 Advanced AI"
      : available ? "Advanced AI 已就绪"
        : state === "failed" ? "Advanced AI 不可用" : "Advanced AI 未安装";

  return <section className="panel" aria-label="Advanced AI status">
    <div className="section-heading">
      <div><span className="eyebrow">ADVANCED AI</span><h2>{title}</h2></div>
      <span className={available ? "status-dot online" : "status-dot"} aria-hidden="true" />
    </div>
    {!available && !installing && <p>
      快速审核仍可直接使用。Advanced AI 是可选组件：安装时需要联网，完成后所有图片审核推理均在本机运行。
    </p>}
    {packageInfo && !installing && <dl className="kv">
      <div><dt>运行环境</dt><dd>{packageInfo.runtime_version}</dd></div>
      <div><dt>模型版本</dt><dd>{packageInfo.model_version}</dd></div>
      <div><dt>预计下载</dt><dd>{bytes(packageInfo.source_bytes)}</dd></div>
      <div><dt>预计安装</dt><dd>{bytes(packageInfo.installed_bytes)}</dd></div>
      <div><dt>所需可用空间</dt><dd>{bytes(packageInfo.required_free_bytes)}</dd></div>
    </dl>}
    {installing && <div aria-live="polite">
      <p>{STEP_LABELS[installStatus?.state ?? ""] ?? "正在处理"}</p>
      <progress max={determinate ? 100 : undefined} value={determinate ? progress : undefined} />
      {determinate && <p>{bytes(installStatus?.bytes_completed ?? 0)} / {bytes(installStatus?.bytes_total ?? 0)}（{progress}%）</p>}
      {onCancelInstall && <button className="button button-secondary" type="button" onClick={onCancelInstall}>取消安装</button>}
    </div>}
    {(operationError || installStatus?.error_message) && <div className="warning" role="alert">
      <span>{operationError ?? installStatus?.error_message}</span>
    </div>}
    {state === "failed" && <div className="warning">
      <span>Advanced AI 已停止，Core 快速审核不受影响。</span>
      <button type="button" onClick={onRestart}>重启 Advanced AI</button>
    </div>}
    <div className="workspace-actions">
      {!available && !installing && packageInfo && onInstall && <button
        className="button button-primary" type="button"
        disabled={!packageInfo.disk_space_sufficient} onClick={onInstall}
      >安装 Advanced AI</button>}
      {!packageInfo && !installing && onSelectPackage && <button className="button button-secondary" type="button" onClick={onSelectPackage}>导入旧版离线包</button>}
      {available && onStop && <button className="button button-secondary" type="button" onClick={onStop}>停止 Advanced AI</button>}
      {snapshot?.runtime_version && onUninstall && <button className="button button-secondary" type="button" onClick={onUninstall}>移除 Advanced AI</button>}
      {onRollback && <button className="button button-secondary" type="button" onClick={onRollback}>回滚上一版本</button>}
    </div>
  </section>;
}
