import { HttpVisionGuardBackend } from "./client";
import { selectedImage } from "../test/fixtures";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("HTTP backend adapter", () => {
  it("checks both liveness and readiness", async () => {
    const transport = vi.fn().mockResolvedValueOnce(jsonResponse({ status: "ok" })).mockResolvedValueOnce(jsonResponse({ status: "ready", components: { pipeline: true } }));
    await expect(new HttpVisionGuardBackend("http://127.0.0.1:9000", transport).health()).resolves.toEqual({ status: "ready", components: { pipeline: true } });
    expect(transport).toHaveBeenNthCalledWith(1, "http://127.0.0.1:9000/health/live", expect.anything());
  });

  it("sends multipart review options", async () => {
    const transport = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    await new HttpVisionGuardBackend("http://127.0.0.1:8000/", transport).review({ image: selectedImage, mode: "full", includeDetails: true });
    const call = transport.mock.calls.at(0);
    expect(call).toBeDefined();
    if (!call) throw new Error("Expected transport call");
    expect(call[0]).toContain("pipeline_mode=full");
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("maps a structured API error", async () => {
    const transport = vi.fn().mockResolvedValue(jsonResponse({ error: { code: "INVALID_IMAGE", message: "bad", request_id: "r", run_id: null, details: null } }, 400));
    await expect(new HttpVisionGuardBackend("http://127.0.0.1:8000", transport).review({ image: selectedImage, mode: "cascaded" })).rejects.toMatchObject({ code: "INVALID_IMAGE", requestId: "r" });
  });

  it("maps an unavailable service", async () => {
    const transport = vi.fn().mockRejectedValue(new TypeError("connection refused"));
    await expect(new HttpVisionGuardBackend("http://127.0.0.1:8000", transport).health()).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
  });
});
