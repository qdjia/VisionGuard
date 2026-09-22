import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RuntimeSetup } from "./RuntimeSetup";
import type { RuntimeController, RuntimeSnapshot } from "../runtime/types";

const failedSnapshot: RuntimeSnapshot = {
  state: "failed",
  backend_mode: "sidecar",
  endpoint: null,
  pid: null,
  elapsed_ms: 4200,
  runtime_version: "0.1.0",
  model_bundle_version: "models-v1",
  api_version: "v1",
  model_components: { detector: "ready", ocr: "missing" },
  diagnostics: {},
  error_code: "MODEL_BUNDLE_MISSING",
  error_message: "VisionGuard AI models are not installed.",
  last_exit_code: 2,
};

describe("Runtime setup screen", () => {
  it("shows structured failure diagnostics without exposing secrets", () => {
    render(<RuntimeSetup snapshot={failedSnapshot} onRestart={vi.fn()} />);
    expect(screen.getByText("MODEL_BUNDLE_MISSING")).toBeInTheDocument();
    expect(screen.getByText("缺失")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "显示诊断信息" }));
    expect(screen.getByText("models-v1")).toBeInTheDocument();
    expect(screen.queryByText(/token/i)).not.toBeInTheDocument();
  });

  it("can request a runtime restart", () => {
    const restart = vi.fn().mockResolvedValue(undefined);
    render(<RuntimeSetup snapshot={{ ...failedSnapshot, error_code: "RUNTIME_START_FAILED" }} onRestart={restart} />);
    fireEvent.click(screen.getByRole("button", { name: "重新启动 Runtime" }));
    expect(restart).toHaveBeenCalledOnce();
  });

  it("installs a validated model bundle before restarting", async () => {
    const restart = vi.fn().mockResolvedValue(undefined);
    const installModelBundle = vi.fn().mockResolvedValue({
      bundle_version: "models-v1",
      validation_status: "ready",
      reused_existing: false,
    });
    const controller: RuntimeController = {
      status: vi.fn(),
      endpoint: vi.fn(),
      restart,
      chooseModelBundle: vi.fn().mockResolvedValue("bundle.zip"),
      inspectModelBundle: vi.fn().mockResolvedValue({
        source_kind: "zip",
        bundle_version: "models-v1",
        runtime_min_inclusive: "0.1.0",
        runtime_max_exclusive: "0.2.0",
        runtime_compatible: true,
        compressed_size_bytes: 10,
        uncompressed_size_bytes: 20,
        validation_status: "selected",
      }),
      installModelBundle,
      modelInstallStatus: vi.fn().mockResolvedValue({
        state: "ready",
        bundle_version: "models-v1",
        error_code: null,
        error_message: null,
      }),
      chooseRuntimeBundle: vi.fn(),
      inspectRuntimeBundle: vi.fn(),
      installRuntimeBundle: vi.fn(),
      runtimeInstallStatus: vi.fn(),
    };
    render(<RuntimeSetup snapshot={failedSnapshot} controller={controller} onRestart={restart} />);
    fireEvent.click(screen.getByRole("button", { name: "选择模型 ZIP" }));
    await screen.findByText("ZIP 模型包");
    fireEvent.click(screen.getByRole("button", { name: "安装并启动 VisionGuard" }));
    await waitFor(() => expect(installModelBundle).toHaveBeenCalledWith("bundle.zip"));
    await waitFor(() => expect(restart).toHaveBeenCalledOnce());
  });

  it("installs a validated GPU runtime before model setup", async () => {
    const restart = vi.fn().mockResolvedValue(undefined);
    const installRuntimeBundle = vi.fn().mockResolvedValue({
      runtime_version: "0.1.0",
      validation_status: "ready",
      reused_existing: false,
    });
    const controller = {
      status: vi.fn(), endpoint: vi.fn(), restart,
      chooseModelBundle: vi.fn(), inspectModelBundle: vi.fn(), installModelBundle: vi.fn(), modelInstallStatus: vi.fn(),
      chooseRuntimeBundle: vi.fn().mockResolvedValue("runtime.zip"),
      inspectRuntimeBundle: vi.fn().mockResolvedValue({
        source_kind: "zip", runtime_version: "0.1.0", platform: "windows", architecture: "x86_64",
        compatible: true, compressed_size_bytes: 10, uncompressed_size_bytes: 20, validation_status: "selected",
      }),
      installRuntimeBundle,
      runtimeInstallStatus: vi.fn(),
    } satisfies RuntimeController;
    render(<RuntimeSetup snapshot={{ ...failedSnapshot, error_code: "RUNTIME_COMPONENT_MISSING" }} controller={controller} onRestart={restart} />);
    fireEvent.click(screen.getByRole("button", { name: "选择 Runtime ZIP" }));
    await screen.findByText("windows / x86_64");
    fireEvent.click(screen.getByRole("button", { name: "安装 GPU Runtime" }));
    await waitFor(() => expect(installRuntimeBundle).toHaveBeenCalledWith("runtime.zip"));
    await waitFor(() => expect(restart).toHaveBeenCalledOnce());
  });
});
