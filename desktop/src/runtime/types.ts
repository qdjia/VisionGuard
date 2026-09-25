export type RuntimeState =
  | "stopped"
  | "starting"
  | "checking_hardware"
  | "validating_models"
  | "launching"
  | "waiting_for_live"
  | "waiting_for_ready"
  | "ready"
  | "unavailable"
  | "failed"
  | "stopping";

export interface RuntimeSnapshot {
  state: RuntimeState;
  backend_mode: string;
  endpoint: string | null;
  pid: number | null;
  elapsed_ms: number;
  runtime_version: string | null;
  model_bundle_version: string | null;
  api_version: string | null;
  model_components: Record<string, string>;
  diagnostics: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  last_exit_code: number | null;
}

export type AdvancedAIState =
  | "not_installed" | "installed" | "stopped" | "starting"
  | "loading_model" | "ready" | "failed" | "stopping";

export interface AdvancedAISnapshot {
  state: AdvancedAIState;
  endpoint: string | null;
  pid: number | null;
  runtime_version: string | null;
  model_bundle_version: string | null;
  model_loaded: boolean;
  model_init_count: number;
  error_code: string | null;
  error_message: string | null;
}

export interface AdvancedAIPackageInfo {
  package_version: string;
  runtime_version: string;
  model_version: string;
  source_bytes: number;
  installed_bytes: number;
  required_free_bytes: number;
  available_free_bytes: number;
  disk_space_sufficient: boolean;
  part_count: number;
  validation_status: string;
}

export interface AdvancedAIInstallStatus {
  state: "idle" | "validating" | "installing" | "activating" | "ready" | "cancelled" | "failed";
  package_version: string | null;
  bytes_completed: number;
  bytes_total: number;
  runtime_version: string | null;
  model_version: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface AdvancedAIInstallResult {
  package_version: string;
  runtime_version: string;
  model_version: string;
  validation_status: string;
}

export interface ModelBundleInfo {
  source_kind: "directory" | "zip";
  bundle_version: string;
  runtime_min_inclusive: string;
  runtime_max_exclusive: string;
  runtime_compatible: boolean;
  compressed_size_bytes: number;
  uncompressed_size_bytes: number;
  validation_status: string;
}

export interface ModelInstallResult {
  bundle_version: string;
  validation_status: string;
  reused_existing: boolean;
}

export interface ModelInstallStatus {
  state: "idle" | "inspecting" | "installing" | "validating" | "ready" | "failed";
  bundle_version: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface RuntimePackageInfo {
  source_kind: "directory" | "zip";
  runtime_version: string;
  platform: string;
  architecture: string;
  compatible: boolean;
  compressed_size_bytes: number;
  uncompressed_size_bytes: number;
  validation_status: string;
}

export interface RuntimeInstallResult {
  runtime_version: string;
  validation_status: string;
  reused_existing: boolean;
}

export interface RuntimeInstallStatus {
  state: "idle" | "inspecting" | "installing" | "validating" | "ready" | "failed";
  runtime_version: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface RuntimeController {
  status(): Promise<RuntimeSnapshot>;
  endpoint(): Promise<string>;
  restart(): Promise<void>;
  chooseModelBundle(kind: "directory" | "zip"): Promise<string | null>;
  inspectModelBundle(source: string): Promise<ModelBundleInfo>;
  installModelBundle(source: string): Promise<ModelInstallResult>;
  modelInstallStatus(): Promise<ModelInstallStatus>;
  chooseRuntimeBundle(kind: "directory" | "zip"): Promise<string | null>;
  inspectRuntimeBundle(source: string): Promise<RuntimePackageInfo>;
  installRuntimeBundle(source: string): Promise<RuntimeInstallResult>;
  runtimeInstallStatus(): Promise<RuntimeInstallStatus>;
  advancedAIStatus?(): Promise<AdvancedAISnapshot>;
  startAdvancedAI?(): Promise<void>;
  restartAdvancedAI?(): Promise<void>;
  stopAdvancedAI?(): Promise<void>;
  chooseAdvancedAIManifest?(): Promise<string | null>;
  inspectAdvancedAIPackage?(manifest: string): Promise<AdvancedAIPackageInfo>;
  installAdvancedAIPackage?(manifest: string): Promise<AdvancedAIInstallResult>;
  advancedAIInstallStatus?(): Promise<AdvancedAIInstallStatus>;
  cancelAdvancedAIInstall?(): Promise<void>;
  uninstallAdvancedAI?(): Promise<void>;
  rollbackAdvancedAI?(): Promise<void>;
}
