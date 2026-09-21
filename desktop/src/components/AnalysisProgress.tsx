import { useEffect, useState } from "react";

export function AnalysisProgress({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const update = () => setElapsed(performance.now() - startedAt);
    update();
    const timer = window.setInterval(update, 100);
    return () => window.clearInterval(timer);
  }, [startedAt]);
  return <div className="analysis-progress" role="status"><span className="spinner" aria-hidden="true" /><div><strong>正在进行多模态分析</strong><p>检测、文字识别与风险推理正在执行 · {(elapsed / 1000).toFixed(1)} s</p></div></div>;
}
