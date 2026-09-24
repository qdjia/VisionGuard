import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import type { AdvancedAISnapshot, AdvancedAIState } from "../runtime/types";
import { AdvancedAIStatus } from "./AdvancedAIStatus";

function snapshot(state: AdvancedAIState): AdvancedAISnapshot {
  return { state, endpoint: null, pid: null, runtime_version: null, model_bundle_version: null, model_loaded: state === "ready", model_init_count: 0, error_code: null, error_message: null };
}

test.each([
  ["not_installed", "未安装"], ["installed", "已安装"],
  ["loading_model", "正在加载"], ["ready", "就绪"], ["failed", "不可用"],
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
