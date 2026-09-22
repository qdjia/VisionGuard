import { invoke } from "@tauri-apps/api/core";

import type { RuntimeController, RuntimeSnapshot } from "./types";

export const tauriRuntimeController: RuntimeController = {
  status: () => invoke<RuntimeSnapshot>("get_runtime_status"),
  endpoint: () => invoke<string>("get_runtime_endpoint"),
  restart: () => invoke<void>("restart_runtime"),
};
