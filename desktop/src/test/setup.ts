import "@testing-library/jest-dom/vitest";

Object.defineProperty(URL, "createObjectURL", { configurable: true, value: () => "blob:preview" });
Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: () => undefined });
Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
