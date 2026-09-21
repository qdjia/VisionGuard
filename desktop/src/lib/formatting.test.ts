import { formatConfidence, formatDuration, formatFileSize, formatRiskScore } from "./formatting";

describe("formatting", () => {
  it("formats durations", () => { expect(formatDuration(18)).toBe("18 ms"); expect(formatDuration(1500)).toBe("1.50 s"); });
  it("formats confidence", () => { expect(formatConfidence(.925)).toBe("92.5%"); expect(formatConfidence(null)).toBe("—"); });
  it("formats risk score without implying probability", () => expect(formatRiskScore(.4567)).toBe("0.457"));
  it("formats file sizes", () => expect(formatFileSize(2 * 1024 ** 2)).toBe("2.0 MB"));
});
