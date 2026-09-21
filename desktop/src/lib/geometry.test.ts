import { scaleBoundingBox, scalePolygon } from "./geometry";

describe("geometry", () => {
  it("scales a bounding box", () => expect(scaleBoundingBox({ x1: 10, y1: 20, x2: 30, y2: 40 }, { width: 100, height: 100 }, { width: 200, height: 50 })).toEqual({ x1: 20, y1: 10, x2: 60, y2: 20 }));
  it("scales a polygon", () => expect(scalePolygon([[10, 20]], { width: 100, height: 100 }, { width: 200, height: 50 })).toEqual([{ x: 20, y: 10 }]));
});
