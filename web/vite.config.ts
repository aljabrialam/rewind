/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Spec 009 — static SPA. The serverless function in `api/` is built by the
// deploy target, not by Vite. Only `VITE_`-prefixed env vars reach the client
// bundle, so no secret can leak (NFR-009-05).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", sourcemap: false },
  test: {
    // vitest runs the api/ unit tests only; the Playwright E2E specs under
    // tests/e2e run via `npm run test:e2e`.
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"],
  },
});
