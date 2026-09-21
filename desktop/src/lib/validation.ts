import { DesktopError } from "../api/errors";
import type { SelectedImage } from "../api/types";

export const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
const allowedMime = new Set(["image/png", "image/jpeg", "image/webp"]);
const allowedExtensions = new Set(["png", "jpg", "jpeg", "webp"]);

function extension(name: string): string {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

export function validateImageFile(file: File): void {
  if (file.size === 0) throw new DesktopError("INVALID_IMAGE");
  if (file.size > MAX_IMAGE_BYTES) throw new DesktopError("UPLOAD_TOO_LARGE");
  if (!allowedMime.has(file.type) || !allowedExtensions.has(extension(file.name))) {
    throw new DesktopError("UNSUPPORTED_MEDIA_TYPE");
  }
}

export async function createSelectedImage(file: File, sourcePath?: string): Promise<SelectedImage> {
  validateImageFile(file);
  const previewUrl = URL.createObjectURL(file);
  try {
    const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
      image.onerror = () => reject(new DesktopError("INVALID_IMAGE"));
      image.src = previewUrl;
    });
    if (dimensions.width <= 0 || dimensions.height <= 0) throw new DesktopError("INVALID_IMAGE");
    return {
      file,
      name: file.name,
      mimeType: file.type,
      size: file.size,
      width: dimensions.width,
      height: dimensions.height,
      previewUrl,
      sourcePath,
    };
  } catch (error) {
    URL.revokeObjectURL(previewUrl);
    throw error;
  }
}

export function releaseSelectedImage(image: SelectedImage | undefined): void {
  if (image) URL.revokeObjectURL(image.previewUrl);
}
