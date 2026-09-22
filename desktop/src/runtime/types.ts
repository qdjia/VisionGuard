export type RuntimeState =
  | "stopped"
  | "starting"
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

export interface RuntimeController {
  status(): Promise<RuntimeSnapshot>;
  endpoint(): Promise<string>;
  restart(): Promise<void>;
}
