import type { BoundingBox } from "../api/types";

export interface Size {
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export function scaleBoundingBox(box: BoundingBox, source: Size, rendered: Size): BoundingBox {
  const scaleX = rendered.width / source.width;
  const scaleY = rendered.height / source.height;
  return {
    x1: box.x1 * scaleX,
    y1: box.y1 * scaleY,
    x2: box.x2 * scaleX,
    y2: box.y2 * scaleY,
  };
}

export function scalePolygon(
  polygon: [number, number][],
  source: Size,
  rendered: Size,
): Point[] {
  const scaleX = rendered.width / source.width;
  const scaleY = rendered.height / source.height;
  return polygon.map(([x, y]) => ({ x: x * scaleX, y: y * scaleY }));
}
