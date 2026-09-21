import type { DesktopError } from "../../api/errors";
import type { PipelineMode, ReviewResponse, SelectedImage } from "../../api/types";

export type ReviewState =
  | { status: "idle"; mode: PipelineMode }
  | { status: "image_selected"; mode: PipelineMode; image: SelectedImage }
  | { status: "submitting" | "analyzing"; mode: PipelineMode; image: SelectedImage; startedAt: number }
  | { status: "completed" | "partial"; mode: PipelineMode; image: SelectedImage; result: ReviewResponse }
  | { status: "failed"; mode: PipelineMode; image?: SelectedImage; error: DesktopError };

export type ReviewAction =
  | { type: "SELECT_IMAGE"; image: SelectedImage }
  | { type: "SET_MODE"; mode: PipelineMode }
  | { type: "SUBMIT"; startedAt: number }
  | { type: "ANALYZING" }
  | { type: "RESOLVE"; result: ReviewResponse }
  | { type: "REJECT"; error: DesktopError }
  | { type: "RESET" };

export function initialReviewState(mode: PipelineMode = "cascaded"): ReviewState {
  return { status: "idle", mode };
}

export function reviewReducer(state: ReviewState, action: ReviewAction): ReviewState {
  switch (action.type) {
    case "SELECT_IMAGE":
      return { status: "image_selected", mode: state.mode, image: action.image };
    case "SET_MODE":
      return { ...state, mode: action.mode };
    case "SUBMIT":
      if (!("image" in state) || !state.image) return state;
      return { status: "submitting", mode: state.mode, image: state.image, startedAt: action.startedAt };
    case "ANALYZING":
      if (state.status !== "submitting") return state;
      return { ...state, status: "analyzing" };
    case "RESOLVE":
      if (!("image" in state) || !state.image) return state;
      return {
        status: action.result.status === "partial" ? "partial" : "completed",
        mode: state.mode,
        image: state.image,
        result: action.result,
      };
    case "REJECT":
      return {
        status: "failed",
        mode: state.mode,
        image: "image" in state ? state.image : undefined,
        error: action.error,
      };
    case "RESET":
      return initialReviewState(state.mode);
  }
}
