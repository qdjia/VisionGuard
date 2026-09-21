import type { ModuleState } from "../api/types";
import { humanize } from "../lib/formatting";

const labels: Record<ModuleState, string> = { success: "已完成", failed: "失败", skipped: "已跳过" };

export function ModuleStatus({ name, status }: { name: string; status: ModuleState }) {
  return <li className="module-row"><span>{humanize(name)}</span><span className={`module-state state-${status}`}>{labels[status]}</span></li>;
}
