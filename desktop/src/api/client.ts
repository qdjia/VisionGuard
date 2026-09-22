import { fetch as tauriFetch } from "@tauri-apps/plugin-http";

import { DesktopError, fromAPIError, normalizeError } from "./errors";
import type {
  APIErrorResponse,
  BackendHealth,
  LiveResponse,
  MetaResponse,
  ReadyResponse,
  ReviewInput,
  ReviewResponse,
  VisionGuardBackend,
} from "./types";
import type { RuntimeController } from "../runtime/types";

export type FetchTransport = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;

const DEFAULT_API_URL = "http://127.0.0.1:8000";

function endpoint(path: string, baseUrl: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function parseError(response: Response): Promise<DesktopError> {
  try {
    return fromAPIError((await response.json()) as APIErrorResponse);
  } catch {
    return new DesktopError(response.status === 503 ? "PIPELINE_NOT_READY" : "UNKNOWN_ERROR", {
      technicalMessage: `HTTP ${response.status} ${response.statusText}`,
    });
  }
}

export class HttpVisionGuardBackend implements VisionGuardBackend {
  constructor(
    private readonly baseUrl: string,
    private readonly transport: FetchTransport = tauriFetch,
  ) {}

  private async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    let response: Response;
    try {
      response = await this.transport(endpoint(path, this.baseUrl), { signal });
    } catch (error) {
      throw normalizeError(error, true);
    }
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as T;
  }

  async health(signal?: AbortSignal): Promise<BackendHealth> {
    const live = await this.get<LiveResponse>("/health/live", signal);
    if (live.status !== "ok") throw new DesktopError("BACKEND_UNAVAILABLE");
    const ready = await this.get<ReadyResponse>("/health/ready", signal);
    return { status: ready.status, components: ready.components };
  }

  meta(signal?: AbortSignal): Promise<MetaResponse> {
    return this.get<MetaResponse>("/v1/meta", signal);
  }

  async review(input: ReviewInput, signal?: AbortSignal): Promise<ReviewResponse> {
    const form = new FormData();
    form.append("file", input.image.file, input.image.name);
    const query = new URLSearchParams({
      pipeline_mode: input.mode,
      include_details: String(input.includeDetails ?? true),
    });
    if (input.saveArtifacts !== undefined) {
      query.set("save_artifacts", String(input.saveArtifacts));
    }
    let response: Response;
    try {
      response = await this.transport(
        endpoint(`/v1/review?${query.toString()}`, this.baseUrl),
        { method: "POST", body: form, signal },
      );
    } catch (error) {
      throw normalizeError(error);
    }
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as ReviewResponse;
  }
}

export function createBackend(baseUrl?: string, transport?: FetchTransport): VisionGuardBackend {
  const resolved = baseUrl ?? import.meta.env.VITE_VISIONGUARD_API_URL ?? DEFAULT_API_URL;
  return new HttpVisionGuardBackend(resolved, transport);
}

export class RuntimeManagedBackend implements VisionGuardBackend {
  constructor(
    private readonly runtime: RuntimeController,
    private readonly transport: FetchTransport = tauriFetch,
  ) {}

  private async client(): Promise<HttpVisionGuardBackend> {
    return new HttpVisionGuardBackend(await this.runtime.endpoint(), this.transport);
  }

  async health(signal?: AbortSignal): Promise<BackendHealth> {
    return (await this.client()).health(signal);
  }

  async meta(signal?: AbortSignal): Promise<MetaResponse> {
    return (await this.client()).meta(signal);
  }

  async review(input: ReviewInput, signal?: AbortSignal): Promise<ReviewResponse> {
    return (await this.client()).review(input, signal);
  }
}

export function createRuntimeManagedBackend(
  runtime: RuntimeController,
  transport?: FetchTransport,
): VisionGuardBackend {
  return new RuntimeManagedBackend(runtime, transport);
}
