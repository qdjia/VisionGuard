import type { BackendHealth, MetaResponse, ReviewInput, ReviewResponse, VisionGuardBackend } from "../api/types";
import type { ImageSource } from "../platform/imageSource";
import { reviewFixture, selectedImage } from "./fixtures";

export class MockBackend implements VisionGuardBackend {
  constructor(public response: ReviewResponse = reviewFixture(), public available = true, public reviewError?: Error) {}
  health(): Promise<BackendHealth> { return this.available ? Promise.resolve({ status: "ready", components: { pipeline: true } }) : Promise.reject(new Error("offline")); }
  meta(): Promise<MetaResponse> { return Promise.resolve({ api_version: "v1", service_version: "1.0.0", pipeline_versions: { full: "v2" }, routing_policy_version: "v1", fusion_policy_version: "v1", prompt_version: "v1", model_identifiers: {}, max_concurrent_inference: 1 }); }
  review = vi.fn((_input: ReviewInput) => { void _input; return this.reviewError ? Promise.reject(this.reviewError) : Promise.resolve(this.response); });
}

export const mockImageSource: ImageSource = {
  select: vi.fn(() => Promise.resolve(selectedImage)),
  subscribeToDrops: vi.fn(() => Promise.resolve(() => undefined)),
};
