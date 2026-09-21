import type { APIErrorResponse } from "./types";

export type DesktopErrorCode = "INVALID_IMAGE" | "UPLOAD_TOO_LARGE" | "UNSUPPORTED_MEDIA_TYPE" | "INVALID_PIPELINE_MODE" | "PIPELINE_NOT_READY" | "INFERENCE_TIMEOUT" | "PIPELINE_FAILURE" | "BACKEND_UNAVAILABLE" | "NETWORK_ERROR" | "UNKNOWN_ERROR";

const messages: Record<DesktopErrorCode, string> = {
  INVALID_IMAGE: "无法读取这张图片，请选择有效的 PNG、JPEG 或 WebP 图片。",
  UPLOAD_TOO_LARGE: "图片超过 15 MB，请压缩后重试。",
  UNSUPPORTED_MEDIA_TYPE: "暂不支持这种图片格式，请使用 PNG、JPEG 或 WebP。",
  INVALID_PIPELINE_MODE: "所选审核模式当前不可用。",
  PIPELINE_NOT_READY: "AI Runtime 尚未准备完成，请稍后重试。",
  INFERENCE_TIMEOUT: "本次分析用时过长，请稍后手动重试。",
  PIPELINE_FAILURE: "VisionGuard 未能完成这次分析。",
  BACKEND_UNAVAILABLE: "VisionGuard AI Runtime 当前不可用。",
  NETWORK_ERROR: "无法连接到 VisionGuard AI Runtime。",
  UNKNOWN_ERROR: "发生了未预期的问题，请稍后重试。",
};

export class DesktopError extends Error {
  readonly code: DesktopErrorCode;
  readonly technicalMessage?: string;
  readonly requestId?: string;
  readonly runId?: string | null;

  constructor(code: DesktopErrorCode, options: { technicalMessage?: string; requestId?: string; runId?: string | null } = {}) {
    super(messages[code]);
    this.name = "DesktopError";
    this.code = code;
    this.technicalMessage = options.technicalMessage;
    this.requestId = options.requestId;
    this.runId = options.runId;
  }
}

const knownCodes = new Set<DesktopErrorCode>(Object.keys(messages) as DesktopErrorCode[]);

export function fromAPIError(response: APIErrorResponse): DesktopError {
  const candidate = response.error.code as DesktopErrorCode;
  return new DesktopError(knownCodes.has(candidate) ? candidate : "UNKNOWN_ERROR", {
    technicalMessage: response.error.message,
    requestId: response.error.request_id,
    runId: response.error.run_id,
  });
}

export function normalizeError(error: unknown, unavailable = false): DesktopError {
  if (error instanceof DesktopError) return error;
  return new DesktopError(unavailable ? "BACKEND_UNAVAILABLE" : "NETWORK_ERROR", {
    technicalMessage: error instanceof Error ? error.message : String(error),
  });
}
