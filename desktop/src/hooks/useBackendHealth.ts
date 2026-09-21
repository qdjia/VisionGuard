import { useCallback, useEffect, useState } from "react";

import type { MetaResponse, VisionGuardBackend } from "../api/types";

export type HealthStatus = "checking" | "ready" | "unavailable";

export function useBackendHealth(backend: VisionGuardBackend) {
  const [status, setStatus] = useState<HealthStatus>("checking");
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const check = useCallback(async () => {
    try {
      await backend.health();
      setStatus("ready");
      try { setMeta(await backend.meta()); } catch { setMeta(null); }
    } catch { setStatus("unavailable"); }
  }, [backend]);
  useEffect(() => {
    const initial = window.setTimeout(() => void check(), 0);
    const timer = window.setInterval(() => void check(), 10_000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, [check]);
  return { status, meta, refresh: check };
}
