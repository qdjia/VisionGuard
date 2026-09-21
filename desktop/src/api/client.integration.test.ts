import { readFile } from "node:fs/promises";

import { HttpVisionGuardBackend } from "./client";
import type { SelectedImage } from "./types";

const enabled = import.meta.env.VITE_VISIONGUARD_INTEGRATION === "1";
const baseUrl = import.meta.env.VITE_VISIONGUARD_API_URL ?? "http://127.0.0.1:8000";
const fixture = (path: string) => new URL(`../../../data/${path}`, import.meta.url);

function image(name: string, bytes: Uint8Array, type = "image/png"): SelectedImage {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return { file: new File([buffer], name, { type }), name, mimeType: type, size: bytes.length, width: 1, height: 1, previewUrl: "blob:integration" };
}

describe.runIf(enabled)("running FastAPI integration", () => {
  const backend = new HttpVisionGuardBackend(baseUrl, globalThis.fetch);
  it("reports a ready runtime", async () => expect((await backend.health()).status).toBe("ready"));
  it("returns a structured safe-image review", async () => { const bytes = await readFile(fixture("vlm_eval/safe.png")); const result = await backend.review({ image: image("safe.png", bytes), mode: "cascaded" }); expect(result.api_version).toBe("v1"); expect(typeof result.result.requires_manual_review).toBe("boolean"); });
  it("supports the full path used for risky images", async () => { const bytes = await readFile(fixture("vlm_eval/risky.png")); const result = await backend.review({ image: image("risky.png", bytes), mode: "full" }); expect(result.metadata.pipeline_mode).toBe("full"); expect(["success", "failed"]).toContain(result.modules.vlm); });
  it("exposes a real cascaded fast path", async () => { const bytes = await readFile(fixture("ocr_smoke/chinese.png")); const result = await backend.review({ image: image("fast-path.png", bytes), mode: "cascaded" }); expect(result.routing).toMatchObject({ route: "fast_path", call_vlm: false }); expect(result.modules.vlm).toBe("skipped"); });
  it("rejects invalid uploads", async () => await expect(backend.review({ image: image("broken.png", new Uint8Array([1, 2, 3])), mode: "cascaded" })).rejects.toMatchObject({ code: "INVALID_IMAGE" }));
});
