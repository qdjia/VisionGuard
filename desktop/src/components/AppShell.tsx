import type { ReactNode } from "react";
import type { HealthStatus } from "../hooks/useBackendHealth";

const healthLabels: Record<HealthStatus, string> = { checking: "正在连接 AI Runtime", ready: "AI Runtime 已就绪", unavailable: "AI Runtime 不可用" };

export function AppShell({ health, onSettings, onAbout, children }: { health: HealthStatus; onSettings: () => void; onAbout: () => void; children: ReactNode }) {
  return <div className="app-shell"><header className="app-header"><div className="brand"><span className="brand-mark">V</span><div><strong>VisionGuard</strong><small>智能出版内容审核</small></div></div><div className="header-actions"><span className={`health health-${health}`}><i />{healthLabels[health]}</span><button className="icon-button" onClick={onSettings} aria-label="设置">设置</button><button className="icon-button" onClick={onAbout} aria-label="关于 VisionGuard">关于</button></div></header><main>{children}</main></div>;
}
