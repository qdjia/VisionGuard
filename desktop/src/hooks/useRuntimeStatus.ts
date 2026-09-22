import { useCallback, useEffect, useState } from "react";

import type { RuntimeController, RuntimeSnapshot } from "../runtime/types";

export function useRuntimeStatus(controller?: RuntimeController) {
  const [snapshot, setSnapshot] = useState<RuntimeSnapshot | null>(null);
  const refresh = useCallback(async () => {
    if (!controller) return;
    try {
      setSnapshot(await controller.status());
    } catch {
      setSnapshot(null);
    }
  }, [controller]);
  const restart = useCallback(async () => {
    if (!controller) return;
    await controller.restart();
    await refresh();
  }, [controller, refresh]);
  useEffect(() => {
    if (!controller) return;
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 750);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [controller, refresh]);
  return { snapshot, refresh, restart };
}
