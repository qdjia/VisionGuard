import { useCallback, useEffect, useState } from "react";

import type { AdvancedAISnapshot, RuntimeController } from "../runtime/types";

export function useAdvancedAIStatus(controller?: RuntimeController) {
  const [snapshot, setSnapshot] = useState<AdvancedAISnapshot | null>(null);
  const refresh = useCallback(async () => {
    if (!controller?.advancedAIStatus) return;
    try { setSnapshot(await controller.advancedAIStatus()); } catch { setSnapshot(null); }
  }, [controller]);
  const restart = useCallback(async () => {
    await controller?.restartAdvancedAI?.();
    await refresh();
  }, [controller, refresh]);
  const stop = useCallback(async () => {
    await controller?.stopAdvancedAI?.();
    await refresh();
  }, [controller, refresh]);
  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 1000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, [refresh]);
  return { snapshot, refresh, restart, stop };
}
