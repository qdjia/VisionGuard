import { reviewFixture, selectedImage } from "../../test/fixtures";
import { initialReviewState, reviewReducer } from "./state";

describe("review state machine", () => {
  it("moves through selected and analyzing", () => { const selected = reviewReducer(initialReviewState(), { type: "SELECT_IMAGE", image: selectedImage }); const running = reviewReducer(selected, { type: "SUBMIT", startedAt: 1 }); expect(running.status).toBe("submitting"); expect(reviewReducer(running, { type: "ANALYZING" }).status).toBe("analyzing"); });
  it("preserves mode when selecting another image", () => { const deep = reviewReducer(initialReviewState(), { type: "SET_MODE", mode: "full" }); expect(reviewReducer(deep, { type: "SELECT_IMAGE", image: selectedImage }).mode).toBe("full"); });
  it("represents partial completion explicitly", () => { const selected = reviewReducer(initialReviewState(), { type: "SELECT_IMAGE", image: selectedImage }); expect(reviewReducer(selected, { type: "RESOLVE", result: reviewFixture({ status: "partial" }) }).status).toBe("partial"); });
});
