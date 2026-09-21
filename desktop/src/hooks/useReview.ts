import { useCallback, useEffect, useReducer, useRef } from "react";

import { normalizeError } from "../api/errors";
import type { PipelineMode, SelectedImage, VisionGuardBackend } from "../api/types";
import { initialReviewState, reviewReducer } from "../features/review/state";
import { releaseSelectedImage } from "../lib/validation";
import type { ImageSource } from "../platform/imageSource";

export function useReview(backend: VisionGuardBackend, imageSource: ImageSource, initialMode: PipelineMode = "cascaded") {
  const [state, dispatch] = useReducer(reviewReducer, initialMode, initialReviewState);
  const imageRef = useRef<SelectedImage | undefined>(undefined);
  const inFlightRef = useRef(false);
  const acceptImage = useCallback((image: SelectedImage) => {
    releaseSelectedImage(imageRef.current);
    imageRef.current = image;
    dispatch({ type: "SELECT_IMAGE", image });
  }, []);
  const selectImage = useCallback(async () => {
    try { const image = await imageSource.select(); if (image) acceptImage(image); }
    catch (error) { dispatch({ type: "REJECT", error: normalizeError(error) }); }
  }, [acceptImage, imageSource]);
  useEffect(() => {
    let active = true;
    let unlisten: (() => void) | undefined;
    void imageSource.subscribeToDrops(acceptImage, (error) => {
      dispatch({ type: "REJECT", error: normalizeError(error) });
    }).then((dispose) => { if (active) unlisten = dispose; else dispose(); });
    return () => { active = false; unlisten?.(); releaseSelectedImage(imageRef.current); };
  }, [acceptImage, imageSource]);
  const analyze = useCallback(async () => {
    if (inFlightRef.current || !("image" in state) || !state.image) return;
    inFlightRef.current = true;
    const image = state.image;
    dispatch({ type: "SUBMIT", startedAt: performance.now() });
    queueMicrotask(() => dispatch({ type: "ANALYZING" }));
    try {
      dispatch({ type: "RESOLVE", result: await backend.review({ image, mode: state.mode, includeDetails: true }) });
    } catch (error) { dispatch({ type: "REJECT", error: normalizeError(error) }); }
    finally { inFlightRef.current = false; }
  }, [backend, state]);
  const setMode = useCallback((mode: PipelineMode) => dispatch({ type: "SET_MODE", mode }), []);
  return { state, selectImage, acceptImage, analyze, setMode };
}
