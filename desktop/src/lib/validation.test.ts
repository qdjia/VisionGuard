import { DesktopError } from "../api/errors";
import { MAX_IMAGE_BYTES, validateImageFile } from "./validation";

describe("image validation", () => {
  it("accepts supported images", () => expect(() => validateImageFile(new File(["x"], "x.png", { type: "image/png" }))).not.toThrow());
  it("rejects empty images", () => expect(() => validateImageFile(new File([], "x.png", { type: "image/png" }))).toThrow(DesktopError));
  it("rejects unsupported formats", () => expect(() => validateImageFile(new File(["x"], "x.gif", { type: "image/gif" }))).toThrow("暂不支持"));
  it("rejects oversized images", () => { const file = new File([new Uint8Array(MAX_IMAGE_BYTES + 1)], "x.png", { type: "image/png" }); expect(() => validateImageFile(file)).toThrow("15 MB"); });
});
