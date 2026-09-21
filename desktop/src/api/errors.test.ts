import { DesktopError, fromAPIError, normalizeError } from "./errors";

describe("desktop errors", () => {
  it("maps structured API errors", () => { const error = fromAPIError({ error: { code: "INFERENCE_TIMEOUT", message: "timeout", request_id: "r", run_id: "run", details: null } }); expect(error.message).toContain("用时过长"); expect(error.requestId).toBe("r"); });
  it("does not expose unknown server messages as user copy", () => { const error = fromAPIError({ error: { code: "SECRET_FAILURE", message: "internal stack", request_id: "r", run_id: null, details: null } }); expect(error.message).toContain("未预期"); expect(error.technicalMessage).toBe("internal stack"); });
  it("normalizes transport failures", () => expect(normalizeError(new Error("refused"), true)).toMatchObject({ code: "BACKEND_UNAVAILABLE", technicalMessage: "refused" }));
  it("preserves known desktop errors", () => { const original = new DesktopError("INVALID_IMAGE"); expect(normalizeError(original)).toBe(original); });
});
