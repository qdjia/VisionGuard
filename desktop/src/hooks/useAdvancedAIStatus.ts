import { useCallback, useEffect, useState } from "react";

import type {
  AdvancedAIInstallStatus,
  AdvancedAIPackageInfo,
  AdvancedAISnapshot,
  RuntimeController,
} from "../runtime/types";

export function useAdvancedAIStatus(controller?: RuntimeController) {
  const [snapshot, setSnapshot] = useState<AdvancedAISnapshot | null>(null);
  const [installStatus, setInstallStatus] = useState<AdvancedAIInstallStatus | null>(null);
  const [packageInfo, setPackageInfo] = useState<AdvancedAIPackageInfo | null>(null);
  const [manifest, setManifest] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    if (!controller?.advancedAIStatus) return;
    try {
      setSnapshot(await controller.advancedAIStatus());
      if (controller.advancedAIInstallStatus) setInstallStatus(await controller.advancedAIInstallStatus());
      if (controller.inspectAdvancedAIOnline && !packageInfo) {
        setPackageInfo(await controller.inspectAdvancedAIOnline());
      }
    } catch { setSnapshot(null); }
  }, [controller, packageInfo]);
  const restart = useCallback(async () => {
    await controller?.restartAdvancedAI?.();
    await refresh();
  }, [controller, refresh]);
  const stop = useCallback(async () => {
    await controller?.stopAdvancedAI?.();
    await refresh();
  }, [controller, refresh]);
  const selectPackage = useCallback(async () => {
    if (!controller?.chooseAdvancedAIManifest || !controller.inspectAdvancedAIPackage) return;
    setOperationError(null);
    const selected = await controller.chooseAdvancedAIManifest();
    if (!selected) return;
    try {
      setPackageInfo(await controller.inspectAdvancedAIPackage(selected));
      setManifest(selected);
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error));
    }
  }, [controller]);
  const install = useCallback(async () => {
    if (packageInfo && !window.confirm(
      `Advanced AI 需要联网下载约 ${(packageInfo.source_bytes / 1024 ** 3).toFixed(2)} GiB，` +
      `并需要约 ${(packageInfo.required_free_bytes / 1024 ** 3).toFixed(2)} GiB 可用空间。安装后审核推理仍完全在本机运行。是否继续？`
    )) return;
    setOperationError(null);
    try {
      if (controller?.installAdvancedAIOnline) await controller.installAdvancedAIOnline();
      else if (controller?.installAdvancedAIPackage && manifest) {
        await controller.installAdvancedAIPackage(manifest);
      } else return;
    }
    catch (error) { setOperationError(error instanceof Error ? error.message : String(error)); }
    await refresh();
  }, [controller, manifest, packageInfo, refresh]);
  const cancelInstall = useCallback(async () => {
    await controller?.cancelAdvancedAIInstall?.();
    await refresh();
  }, [controller, refresh]);
  const uninstall = useCallback(async () => {
    setOperationError(null);
    try { await controller?.uninstallAdvancedAI?.(); }
    catch (error) { setOperationError(error instanceof Error ? error.message : String(error)); }
    setPackageInfo(null);
    setManifest(null);
    await refresh();
  }, [controller, refresh]);
  const rollback = useCallback(async () => {
    setOperationError(null);
    try { await controller?.rollbackAdvancedAI?.(); }
    catch (error) { setOperationError(error instanceof Error ? error.message : String(error)); }
    await refresh();
  }, [controller, refresh]);
  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 1000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, [refresh]);
  return {
    snapshot, installStatus, packageInfo, operationError,
    refresh, restart, stop, selectPackage, install, cancelInstall, uninstall, rollback,
  };
}
