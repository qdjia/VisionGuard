import { fireEvent, render, screen } from "@testing-library/react";

import { RuntimeSetup } from "./RuntimeSetup";
import type { RuntimeSnapshot } from "../runtime/types";

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
    render(<RuntimeSetup snapshot={failedSnapshot} onRestart={restart} />);
    fireEvent.click(screen.getByRole("button", { name: "重新启动 Runtime" }));
    expect(restart).toHaveBeenCalledOnce();
  });
});
