import { defineConfig, devices } from "@playwright/test";

// Spec 009 — one scripted end-to-end pass over the hosted console's demonstration
// path (Constitution Article VI, "Top — E2E"). Behaviour + DOM + network only;
// no pixel or layout assertions (Article VI, "UI rendering … is not tested").
//
// Runs against the Vite dev server. The dev server has no /api route, so tests
// that need a "live" fixture stub it with page.route(); the fallback tests let
// it fall through to the bundled public/tree.json.

const PORT = 4188;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
