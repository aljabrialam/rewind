import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Spec 009 — static SPA. The serverless function in `api/` is built by the
// deploy target, not by Vite. Only `VITE_`-prefixed env vars reach the client
// bundle, so no secret can leak (NFR-009-05).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", sourcemap: false },
});
