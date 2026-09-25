import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import type { AdvancedAISnapshot, AdvancedAIState } from "../runtime/types";
import { AdvancedAIStatus } from "./AdvancedAIStatus";

function snapshot(state: AdvancedAIState): AdvancedAISnapshot {
  return { state, endpoint: null, pid: null, runtime_version: null, model_bundle_version: null, model_loaded: state === "ready", model_init_count: 0, error_code: null, error_message: null };
}

test.each([
  ["not_installed", "Advanced AI 未安装"], ["installed", "Advanced AI 未安装"],
  ["loading_model", "正在加载 Advanced AI"], ["ready", "Advanced AI 已就绪"], ["failed", "Advanced AI 不可用"],
] as [AdvancedAIState, string][])("renders %s product state", (state, label) => {
  render(<AdvancedAIStatus snapshot={snapshot(state)} available={state === "ready"} onRestart={() => undefined} />);
  expect(screen.getByRole("heading", { name: label })).toBeInTheDocument();
});

test("offers an isolated restart after failure", () => {
  const restart = vi.fn();
  render(<AdvancedAIStatus snapshot={snapshot("failed")} available={false} onRestart={restart} />);
  fireEvent.click(screen.getByRole("button", { name: "重启 Advanced AI" }));
  expect(restart).toHaveBeenCalledOnce();
});

test("renders real byte progress and supports cancellation", () => {
  const cancel = vi.fn();
  render(<AdvancedAIStatus
    snapshot={snapshot("stopped")}
    available={false}
    installStatus={{
      state: "installing", package_version: "v1", bytes_completed: 1024 ** 3,
      bytes_total: 2 * 1024 ** 3, runtime_version: null, model_version: null,
      error_code: null, error_message: null,
    }}
    onRestart={() => undefined}
    onCancelInstall={cancel}
  />);
  expect(screen.getByText(/1.00 GiB \/ 2.00 GiB/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "取消安装" }));
  expect(cancel).toHaveBeenCalledOnce();
});
