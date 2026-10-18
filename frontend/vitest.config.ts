import { fileURLToPath, URL } from "node:url"

import { defineConfig } from "vitest/config"

// Mirrors the alias from vite.config.ts so tests can resolve "@/...".
export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
})
