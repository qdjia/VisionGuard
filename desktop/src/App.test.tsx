import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { reviewFixture } from "./test/fixtures";
import { MockBackend, mockImageSource } from "./test/mocks";

async function selectAndReview(backend = new MockBackend()) {
  const user = userEvent.setup();
  render(<App backend={backend} imageSource={mockImageSource} />);
  await waitFor(() => expect(screen.getByText("AI Runtime 已就绪")).toBeInTheDocument());
  await user.click(screen.getByRole("button", { name: "选择图片" }));
  await user.click(screen.getByRole("button", { name: "开始审核" }));
  await screen.findByText("审核结论");
  return { user, backend };
}

describe("VisionGuard desktop", () => {
  beforeEach(() => localStorage.clear());

  it("starts with a native image selection entry point", () => {
    render(<App backend={new MockBackend()} imageSource={mockImageSource} />);
    expect(screen.getByText("拖入出版图片开始审核")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择图片" })).toBeEnabled();
  });

  it("keeps analysis disabled until runtime is ready", async () => {
    const user = userEvent.setup();
    render(<App backend={new MockBackend(reviewFixture(), false)} imageSource={mockImageSource} />);
    await user.click(screen.getByRole("button", { name: "选择图片" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "开始审核" })).toBeDisabled());
  });

  it("submits the default fast mode", async () => {
    const { backend } = await selectAndReview();
    expect(backend.review).toHaveBeenCalledWith(expect.objectContaining({ mode: "cascaded", includeDetails: true }));
  });

  it("supports full analysis mode", async () => {
    const backend = new MockBackend(reviewFixture({ metadata: { pipeline_mode: "full", pipeline_version: "v2", routing_policy_version: "v1", fusion_policy_version: "v1", prompt_version: "v1" } }));
    const user = userEvent.setup(); render(<App backend={backend} imageSource={mockImageSource} />);
    await waitFor(() => expect(screen.getByText("AI Runtime 已就绪")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /深度模式/ }));
    await user.click(screen.getByRole("button", { name: "选择图片" }));
    await user.click(screen.getByRole("button", { name: "开始审核" }));
    await waitFor(() => expect(backend.review).toHaveBeenCalledWith(expect.objectContaining({ mode: "full" })));
  });

  it("deduplicates repeated analyze clicks", async () => {
    const backend = new MockBackend();
    backend.review.mockImplementation(() => new Promise(() => undefined));
    const user = userEvent.setup();
    render(<App backend={backend} imageSource={mockImageSource} />);
    await waitFor(() => expect(screen.getByText("AI Runtime 已就绪")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "选择图片" }));
    const analyze = screen.getByRole("button", { name: "开始审核" });
    fireEvent.click(analyze);
    fireEvent.click(analyze);
    expect(backend.review).toHaveBeenCalledTimes(1);
  });

  it("shows a low-risk result and score disclaimer", async () => {
    await selectAndReview();
    expect(screen.getByText("低风险")).toBeInTheDocument();
    expect(screen.getByText(/不等同于违规概率/)).toBeInTheDocument();
  });

  it("shows a high-risk result with explicit text", async () => {
    const fixture = reviewFixture();
    fixture.result = { ...fixture.result, risk_level: "high", risk_score: .91, requires_manual_review: true, categories: [{ name: "weapon", score: .88 }] };
    await selectAndReview(new MockBackend(fixture));
    expect(screen.getByText("高风险")).toBeInTheDocument();
    expect(screen.getByText(/weapon/)).toBeInTheDocument();
  });

  it("shows partial-result warning", async () => {
    await selectAndReview(new MockBackend(reviewFixture({ status: "partial" })));
    expect(screen.getByRole("alert")).toHaveTextContent("当前结论可能不完整");
  });

  it("shows detection and OCR evidence tabs", async () => {
    const { user } = await selectAndReview();
    await user.click(screen.getByRole("tab", { name: "目标检测" }));
    expect(screen.getByText("weapon")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "文字识别" }));
    expect(screen.getAllByText("测试文本").length).toBeGreaterThan(0);
  });

  it("explains a skipped VLM fast path", async () => {
    const { user } = await selectAndReview();
    await user.click(screen.getByRole("tab", { name: "AI 审核" }));
    expect(screen.getByText("本次未调用视觉语言模型")).toBeInTheDocument();
  });

  it("renders server text as text rather than HTML", async () => {
    const fixture = reviewFixture();
    fixture.result.reason = "<img src=x onerror=alert(1)>";
    await selectAndReview(new MockBackend(fixture));
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("escapes VLM reason and evidence", async () => {
    const fixture = reviewFixture();
    fixture.modules.vlm = "success";
    fixture.details!.vlm_reason = "<script>alert('vlm')</script>";
    fixture.details!.vlm_evidence = [{ type: "semantic", description: "<img src=x onerror=alert(2)>", bbox: null, text: null }];
    const { user } = await selectAndReview(new MockBackend(fixture));
    await user.click(screen.getByRole("tab", { name: "AI 审核" }));
    expect(screen.getByText("<script>alert('vlm')</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("can hide technical details", async () => {
    const { user } = await selectAndReview();
    await user.click(screen.getByRole("button", { name: "设置" }));
    fireEvent.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("tab", { name: "技术详情" })).not.toBeInTheDocument();
  });
});
