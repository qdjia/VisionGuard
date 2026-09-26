import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

import type {
  AdvancedAISnapshot,
  AdvancedAIInstallResult,
  AdvancedAIInstallStatus,
  AdvancedAIPackageInfo,
  ModelBundleInfo,
  ModelInstallResult,
  ModelInstallStatus,
  RuntimeInstallResult,
  RuntimeInstallStatus,
  RuntimePackageInfo,
  RuntimeController,
  RuntimeSnapshot,
} from "./types";

export const tauriRuntimeController: RuntimeController = {
  status: () => invoke<RuntimeSnapshot>("get_runtime_status"),
  endpoint: () => invoke<string>("get_runtime_endpoint"),
  restart: () => invoke<void>("restart_runtime"),
  chooseModelBundle: async (kind) => {
    const selected = await open({
      directory: kind === "directory",
      multiple: false,
      title: kind === "directory" ? "选择已解压的 VisionGuard 模型目录" : "选择 VisionGuard 模型 ZIP",
      filters: kind === "zip" ? [{ name: "VisionGuard 模型包", extensions: ["zip"] }] : undefined,
    });
    return typeof selected === "string" ? selected : null;
  },
  inspectModelBundle: (source) => invoke<ModelBundleInfo>("inspect_model_bundle", { source }),
  installModelBundle: (source) => invoke<ModelInstallResult>("install_model_bundle", { source }),
  modelInstallStatus: () => invoke<ModelInstallStatus>("get_model_install_status"),
  chooseRuntimeBundle: async (kind) => {
    const selected = await open({
      directory: kind === "directory",
      multiple: false,
      title: kind === "directory" ? "选择已解压的 VisionGuard GPU Runtime" : "选择 VisionGuard GPU Runtime ZIP",
      filters: kind === "zip" ? [{ name: "VisionGuard GPU Runtime", extensions: ["zip"] }] : undefined,
    });
    return typeof selected === "string" ? selected : null;
  },
  inspectRuntimeBundle: (source) => invoke<RuntimePackageInfo>("inspect_runtime_bundle", { source }),
  installRuntimeBundle: (source) => invoke<RuntimeInstallResult>("install_runtime_bundle", { source }),
  runtimeInstallStatus: () => invoke<RuntimeInstallStatus>("get_runtime_install_status"),
  advancedAIStatus: () => invoke<AdvancedAISnapshot>("get_advanced_ai_status"),
  startAdvancedAI: () => invoke<void>("start_advanced_ai"),
  restartAdvancedAI: () => invoke<void>("restart_advanced_ai"),
  stopAdvancedAI: () => invoke<void>("stop_advanced_ai"),
  chooseAdvancedAIManifest: async () => {
    const selected = await open({
      directory: false,
      multiple: false,
      title: "选择 Advanced AI 安装清单",
      filters: [{ name: "Advanced AI Manifest", extensions: ["json"] }],
    });
    return typeof selected === "string" ? selected : null;
  },
  inspectAdvancedAIPackage: (manifest) => invoke<AdvancedAIPackageInfo>("inspect_advanced_ai_package", { manifest }),
  installAdvancedAIPackage: (manifest) => invoke<AdvancedAIInstallResult>("install_advanced_ai_package", { manifest }),
  inspectAdvancedAIOnline: () => invoke<AdvancedAIPackageInfo>("inspect_advanced_ai_online"),
  installAdvancedAIOnline: () => invoke<AdvancedAIInstallResult>("install_advanced_ai_online"),
  advancedAIInstallStatus: () => invoke<AdvancedAIInstallStatus>("get_advanced_ai_install_status"),
  cancelAdvancedAIInstall: () => invoke<void>("cancel_advanced_ai_install"),
  uninstallAdvancedAI: () => invoke<void>("uninstall_advanced_ai"),
  rollbackAdvancedAI: () => invoke<void>("rollback_advanced_ai"),
};
