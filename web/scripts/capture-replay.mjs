// Capture the hosted console's replay as presentation assets.
//   node scripts/capture-replay.mjs [url]
// Output: web/artifacts/replay.webm  + web/artifacts/NN-<slug>.png (one per caption)
//
// Runs against the deployed site by default (the replay is client-only, so it
// plays fully with no local server). Pass a URL to point it elsewhere.

import { chromium } from "@playwright/test";
import { mkdir, rm, readdir, rename } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const TARGET = process.argv[2] || "https://rewind-console.vercel.app/";
const OUT = fileURLToPath(new URL("../artifacts/", import.meta.url));
const VIEWPORT = { width: 1280, height: 800 };

const slug = (s) =>
  s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48);

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: VIEWPORT,
  deviceScaleFactor: 2,
  recordVideo: { dir: OUT, size: VIEWPORT },
});
const page = await context.newPage();

console.log(`→ ${TARGET}`);
await page.goto(TARGET, { waitUntil: "networkidle" });
await page.waitForSelector(".rail .node");
await page.waitForTimeout(1200); // let the live view settle on camera

await page.getByRole("button", { name: /replay run/i }).click();

const caption = page.locator(".replayCaption");
await caption.waitFor();

let last = "";
let shot = 0;
const deadline = Date.now() + 40_000;
while (Date.now() < deadline) {
  const replaying = await page.locator(".notice.replay").count();
  if (!replaying) break;
  const text = (await caption.textContent())?.trim() ?? "";
  const body = text.replace(/^\d+\s*\/\s*\d+\s*/, ""); // drop the "3 / 11" chip
  if (body && body !== last) {
    last = body;
    const name = `${String(++shot).padStart(2, "0")}-${slug(body)}.png`;
    await page.screenshot({ path: path.join(OUT, name) });
    console.log(`  ${name}  —  ${body}`);
  }
  await page.waitForTimeout(200);
}

// final "back to live" frame
await page.waitForTimeout(800);
await page.screenshot({ path: path.join(OUT, `${String(++shot).padStart(2, "0")}-back-to-live.png`) });

await context.close(); // flushes the video
await browser.close();

// give the video a stable name
for (const f of await readdir(OUT)) {
  if (f.endsWith(".webm")) {
    await rename(path.join(OUT, f), path.join(OUT, "replay.webm"));
    break;
  }
}
console.log(`\n✓ ${OUT}`);
