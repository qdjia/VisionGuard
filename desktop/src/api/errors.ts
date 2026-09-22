import type { APIErrorResponse } from "./types";

export type DesktopErrorCode = "INVALID_IMAGE" | "UPLOAD_TOO_LARGE" | "UNSUPPORTED_MEDIA_TYPE" | "INVALID_PIPELINE_MODE" | "PIPELINE_NOT_READY" | "INFERENCE_TIMEOUT" | "PIPELINE_FAILURE" | "BACKEND_UNAVAILABLE" | "NETWORK_ERROR" | "RUNTIME_START_FAILED" | "RUNTIME_EXITED" | "RUNTIME_NOT_READY" | "RUNTIME_COMPONENT_MISSING" | "RUNTIME_PACKAGE_INVALID" | "RUNTIME_PACKAGE_INCOMPATIBLE" | "RUNTIME_HASH_MISMATCH" | "RUNTIME_INSTALL_FAILED" | "MODEL_BUNDLE_MISSING" | "MODEL_BUNDLE_INVALID" | "MODEL_BUNDLE_INCOMPATIBLE" | "MODEL_HASH_MISMATCH" | "MODEL_INSTALL_FAILED" | "MODEL_DISK_SPACE_INSUFFICIENT" | "MODEL_VALIDATION_FAILED" | "RUNTIME_VERSION_MISMATCH" | "GPU_REQUIREMENT_NOT_SATISFIED" | "PLATFORM_NOT_SUPPORTED" | "RUNTIME_DISK_SPACE_INSUFFICIENT" | "UNKNOWN_ERROR";

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
  RUNTIME_START_FAILED: "无法启动 VisionGuard AI Runtime。",
  RUNTIME_EXITED: "VisionGuard AI Runtime 意外停止。",
  RUNTIME_NOT_READY: "VisionGuard AI Runtime 尚未完成模型加载。",
  RUNTIME_COMPONENT_MISSING: "VisionGuard GPU Runtime 尚未安装。",
  RUNTIME_PACKAGE_INVALID: "GPU Runtime 包无效或不完整。",
  RUNTIME_PACKAGE_INCOMPATIBLE: "GPU Runtime 与当前 Desktop 或操作系统不兼容。",
  RUNTIME_HASH_MISMATCH: "GPU Runtime 文件校验失败。",
  RUNTIME_INSTALL_FAILED: "GPU Runtime 安装失败，现有版本未被覆盖。",
  MODEL_BUNDLE_MISSING: "VisionGuard AI 模型尚未安装。",
  MODEL_BUNDLE_INVALID: "VisionGuard AI 模型包无效或不完整。",
  MODEL_BUNDLE_INCOMPATIBLE: "模型包与当前 AI Runtime 版本不兼容。",
  MODEL_HASH_MISMATCH: "模型文件校验失败，请重新获取模型包。",
  MODEL_INSTALL_FAILED: "模型安装失败，现有模型未被覆盖。",
  MODEL_DISK_SPACE_INSUFFICIENT: "模型安装空间不足。",
  MODEL_VALIDATION_FAILED: "VisionGuard AI 模型校验失败。",
  RUNTIME_VERSION_MISMATCH: "Desktop 与 AI Runtime 版本不兼容。",
  GPU_REQUIREMENT_NOT_SATISFIED: "GPU Edition 需要 NVIDIA GPU 和兼容驱动。",
  PLATFORM_NOT_SUPPORTED: "当前版本仅支持 64 位 Windows。",
  RUNTIME_DISK_SPACE_INSUFFICIENT: "AI Runtime 用户数据空间不足。",
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
