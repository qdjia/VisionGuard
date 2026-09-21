import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    include: ["src/**/*.integration.test.ts"],
    testTimeout: 180_000,
    hookTimeout: 30_000,
  },
});
