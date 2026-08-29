import { test, expect, type Route } from "@playwright/test";

// Spec 009 — scripted E2E over the hosted console's demonstration path
// (Constitution Article VI "Top — E2E"). Assertions are on behaviour, DOM
// presence and network — never pixels or layout.

// A small but complete run: 4 rail checkpoints (the last fails), 2 fan-out
// branches off s1, a verdict. Branches hang off an earlier checkpoint than the
// failing leaf, matching the real fixture's shape.
const FIXTURE = {
  head: "b0",
  live_sandboxes: 1,
  session_elapsed: 42,
  runtime_version: "v9.9.9",
  verdict: {
    winner: 0,
    reason: "branch b0 exited 0 with usable output",
    provider: "deterministic-fallback",
  },
  nodes: [
    node("root", 0, "(start)", null, ["s1"], 0, "", "ok", null, ""),
    node("s1", 1, "echo 'def add(a,b): return a+b' > calc.py", "root", ["s2"], 0, "", "ok", null, "write it first"),
    node("s2", 2, "echo 'assert add(2,2)==4' > test.py", "s1", ["s3"], 0, "", "ok", null, ""),
    node("s3", 3, "python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"", "s2", [], 1, "AssertionError: boom", "failed", "failed", ""),
    {
      ...node("b0", 4, "fix A && python3 test.py", "s1", [], 0, "PASS", "ok", "done", "candidate A"),
      branch: true,
      progress: { state: "done", elapsed_seconds: 6.8 },
    },
    {
      ...node("b1", 5, "fix B && python3 test.py", "s1", [], 1, "AssertionError", "failed", "failed", "candidate B"),
      branch: true,
      progress: { state: "failed", elapsed_seconds: 6.6 },
    },
  ],
};

function node(
  id: string,
  index: number,
  instruction: string,
  parent: string | null,
  children: string[],
  exit_code: number,
  stdout: string,
  outcome: string,
  terminal: string | null,
  rationale: string,
) {
  return {
    id, index, instruction, parent, children,
    sandbox: `sb-${id}`, state: "live", snapshot: null,
    created_at: "", exit_code, stdout, outcome, terminal, rationale,
  };
}

const serveFixture = (route: Route) =>
  route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FIXTURE) });

test.describe("hosted console", () => {
  test("renders the run from a live fixture, no sample banner", async ({ page }) => {
    await page.route("**/api/fixture", serveFixture);
    await page.goto("/");

    // source === "live" -> no notice rendered at all
    await expect(page.locator(".notice")).toHaveCount(0);

    await expect(page.locator(".rail .node")).toHaveCount(4);
    await expect(page.locator(".lane")).toHaveCount(2);
    // head is the promoted branch (b0) — it shows as the won lane, not a rail node
    await expect(page.locator(".lane.won")).toHaveCount(1);
    await expect(page.locator(".lane.won")).toContainText("promoted");

    await expect(page.locator(".verdict")).toBeVisible();
    await expect(page.locator(".verdict")).toContainText("exited 0 with usable output");

    const footer = page.locator("footer");
    await expect(footer).toContainText("checkpoints 6");
    await expect(footer).toContainText("branches 2");
    await expect(footer).toContainText("v9.9.9");

    // a runtime-issued value renders in the mono face
    await expect(page.locator(".mono", { hasText: "sb-root" }).first()).toBeVisible();
  });

  test("marks the head checkpoint on the rail with a HEAD tag", async ({ page }) => {
    // a run whose head is still a rail checkpoint (no promotion yet)
    const midRun = { ...FIXTURE, head: "s2", verdict: null };
    await page.route("**/api/fixture", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(midRun) }),
    );
    await page.goto("/");

    const head = page.locator(".rail .node.head");
    await expect(head).toHaveCount(1);
    await expect(head).toContainText("assert add(2,2)==4");
    // the "HEAD" badge is a ::after pseudo-element — check its computed content
    const badge = await head.locator(".cmd").evaluate(
      (el) => getComputedStyle(el, "::after").content,
    );
    expect(badge).toContain("HEAD");
    await expect(page.locator(".verdict")).toHaveCount(0);
  });

  test("falls back to the bundled fixture with an honest banner", async ({ page }) => {
    await page.route("**/api/fixture", (route) => route.abort());
    await page.goto("/");

    await expect(page.locator(".notice")).toContainText("sample data — not a live push");
    // still a usable view — the bundled public/tree.json
    await expect(page.locator(".rail .node").first()).toBeVisible();
  });

  test("replay plays the run's stages back, then resumes the live view", async ({ page }) => {
    test.setTimeout(45_000);
    await page.route("**/api/fixture", serveFixture);
    await page.goto("/");

    await page.getByRole("button", { name: /replay run/i }).click();

    await expect(page.locator(".notice.replay")).toContainText("replaying a recorded run");
    await expect(page.getByRole("button", { name: /stop replay · \d+\/9/i })).toBeVisible();

    // plain-language narration is shown and advances with the frames
    await expect(page.locator(".replayCaption")).toBeVisible();
    await expect(page.locator(".replayCaption")).toContainText("calculator");

    // a fan-out frame arrives (rail-reveal frames have no lanes)
    await expect(page.locator(".lane")).toHaveCount(2, { timeout: 20_000 });
    await expect(page.locator(".replayCaption")).toContainText(
      /copies of that machine|machines run their fix|Results are in/,
    );
    // the verdict frame arrives
    await expect(page.locator(".verdict")).toBeVisible({ timeout: 25_000 });
    await expect(page.locator(".replayCaption")).toContainText("Keep the branch that passed");

    // replay ends -> banner gone, button reset, live fixture back on screen
    await expect(page.locator(".notice.replay")).toHaveCount(0, { timeout: 15_000 });
    await expect(page.getByRole("button", { name: /replay run/i })).toBeVisible();
    await expect(page.locator("footer")).toContainText("42.0s");
  });

  test("replay is client-only — it completes with all network blocked", async ({ page }) => {
    test.setTimeout(45_000);
    await page.route("**/api/fixture", serveFixture);
    await page.goto("/");
    await expect(page.locator(".rail .node")).toHaveCount(4);

    // cut every request from here on; replay must still animate every stage
    await page.route("**/*", (route) => route.abort());

    await page.getByRole("button", { name: /replay run/i }).click();
    await expect(page.locator(".notice.replay")).toBeVisible();
    await expect(page.locator(".lane")).toHaveCount(2, { timeout: 20_000 });
    await expect(page.locator(".verdict")).toBeVisible({ timeout: 25_000 });
  });

  test("selecting a checkpoint shows its evidence; restore records a request, no runtime call", async ({
    page,
  }) => {
    const external: string[] = [];
    page.on("request", (r) => {
      const u = r.url();
      if (!u.startsWith("http://localhost:4188") && !u.startsWith("data:")) external.push(u);
    });

    await page.route("**/api/fixture", serveFixture);
    await page.goto("/");

    await page.locator(".rail .node", { hasText: "exec(open('test.py')" }).click();
    await expect(page.locator("pre")).toContainText("AssertionError: boom");
    await expect(page.locator(".exit")).toContainText("exit code");
    await expect(page.locator(".exit")).toContainText("1");

    await page.getByRole("button", { name: /restore to this checkpoint/i }).click();
    const row = page.locator(".reqs .r");
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("restore");
    await expect(row).toContainText("s3");

    // the console never reaches out to a runtime — only its own origin
    expect(external).toEqual([]);
  });
});
