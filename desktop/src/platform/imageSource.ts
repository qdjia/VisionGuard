import { getCurrentWebview } from "@tauri-apps/api/webview";
import { open } from "@tauri-apps/plugin-dialog";
import { readFile } from "@tauri-apps/plugin-fs";

import type { SelectedImage } from "../api/types";
import { createSelectedImage } from "../lib/validation";

export interface ImageSource {
  select(): Promise<SelectedImage | null>;
  subscribeToDrops(
    handler: (image: SelectedImage) => void,
    onError?: (error: unknown) => void,
  ): Promise<() => void>;
}

function fileName(path: string): string {
  return path.replaceAll("\\", "/").split("/").pop() ?? "image";
}

function mimeFromName(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "png") return "image/png";
  if (ext === "webp") return "image/webp";
  return "image/jpeg";
}

async function loadPath(path: string): Promise<SelectedImage> {
  const name = fileName(path);
  const bytes = await readFile(path);
  return createSelectedImage(new File([bytes], name, { type: mimeFromName(name) }), path);
}

export const tauriImageSource: ImageSource = {
  async select() {
    const selected = await open({
      multiple: false,
      directory: false,
      title: "选择要审核的图片",
      filters: [{ name: "图片", extensions: ["png", "jpg", "jpeg", "webp"] }],
    });
    return selected ? loadPath(selected) : null;
  },
  async subscribeToDrops(handler, onError) {
    return getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type !== "drop") return;
      const [path] = event.payload.paths;
      if (path) void loadPath(path).then(handler).catch(onError);
    });
  },
};
