import { isBranchNode, type BranchState, type ConsoleFixture, type RailNode } from "./types";

// Spec 009 — the Replay button. Pure client-side: it takes the current fixture
// (the last real run pushed to the console, or the bundled one) and derives a
// short sequence of frames that replays the run's shape through the same
// components — seed steps filling in, a step failing, the head jumping back,
// three branches fanning out, then the verdict. No engine, no network.
//
// Each frame also carries a plain-language `caption` so a non-technical audience
// can follow the replay without reading shell commands (FR-009-11).

export const REPLAY_FRAME_MS = 1500;
export const REPLAY_HOLD_MS = 2600; // linger on the final frame before releasing

export type ReplayFrame = {
  fixture: ConsoleFixture;
  /** short, plain-language narration for the beat this frame shows */
  caption: string;
};

// Instruction → narration. Ordered; first match wins. Demo-shaped but degrades
// to a trimmed instruction when nothing matches.
const STEP_CAPTIONS: [RegExp, string][] = [
  [/\(start\)/i, "A fresh Linux machine boots up"],
  [/return\s+a\s*\+\s*b/i, "The agent writes a calculator — add(a, b) returns a + b"],
  [/return\s+a\s*-\s*b/i, "The agent edits the calculator — now it returns a − b, a silent mistake"],
  [/return\s+sum\(/i, "A candidate fix — add(a, b) returns sum([a, b])"],
  [/return\s+a\s*\*\s*b/i, "A candidate fix — add(a, b) returns a × b"],
  [/assert\s+add/i, "The agent writes a test — add(2, 2) should equal 4"],
];

function stepCaption(node: RailNode): string {
  for (const [re, text] of STEP_CAPTIONS) if (re.test(node.instruction)) return text;
  if (/print\(\s*['"]PASS/i.test(node.instruction)) {
    return node.exit_code === 0
      ? "The test runs — it passes ✓"
      : "The test runs — it fails ✗  (normally the run dies here)";
  }
  const trimmed = node.instruction.trim();
  return trimmed.length > 68 ? `${trimmed.slice(0, 68)}…` : trimmed;
}

function frame(
  nodes: RailNode[],
  head: string,
  verdict: ConsoleFixture["verdict"],
  live: number,
  elapsed: number,
  runtimeVersion: string | undefined,
): ConsoleFixture {
  return {
    head,
    nodes,
    verdict: verdict ?? null,
    live_sandboxes: live,
    session_elapsed: Math.round(elapsed * 10) / 10,
    runtime_version: runtimeVersion,
  };
}

/**
 * Derive replay frames from a finished run fixture. Falls back gracefully: with
 * no branch nodes it just reveals the rail one checkpoint at a time.
 */
export function buildReplayFrames(fin: ConsoleFixture): ReplayFrame[] {
  const all = fin.nodes ?? [];
  if (all.length === 0) return [{ fixture: fin, caption: "Waiting for a run" }];

  const rail = all.filter((n) => !isBranchNode(n, all));
  const branches = all.filter((n) => isBranchNode(n, all));
  const rv = fin.runtime_version;
  const frames: ReplayFrame[] = [];
  let t = 0;

  // 1 — seed steps appear one by one; head follows the newest.
  for (let i = 1; i <= rail.length; i++) {
    const shown = rail.slice(0, i);
    const step = shown[shown.length - 1];
    t += 3.1;
    frames.push({
      fixture: frame(shown, step.id, null, 1, t, rv),
      caption: stepCaption(step),
    });
  }

  if (branches.length === 0) {
    frames.push({
      fixture: frame(rail, fin.head, fin.verdict ?? null, fin.live_sandboxes ?? 0, t, rv),
      caption: "The run so far",
    });
    return frames;
  }

  // 2 — rewind: the head jumps back to the last good checkpoint (the branch
  //     parent), the failing tail still visible on the rail.
  const parentId =
    branches[0].parent ??
    rail[Math.max(0, rail.length - 3)]?.id ??
    fin.head;
  t += 1.4;
  frames.push({
    fixture: frame(rail, parentId, null, 1, t, rv),
    caption: "Rewind to the last checkpoint that worked — before the mistake",
  });

  // 3 — fan-out: branches, cycling creating -> running -> done.
  const n = branches.length;
  const stagePlan: { stage: BranchState; caption: string }[] = [
    { stage: "creating", caption: `Make ${n} copies of that machine — one per candidate fix` },
    { stage: "running", caption: `${n} machines run their fix at the same time` },
    { stage: "done", caption: "Results are in — judged on exit codes, not on what the agent claims" },
  ];
  for (const { stage, caption } of stagePlan) {
    t += stage === "creating" ? 6.8 : 3.4;
    const laneNodes = branches.map((b) => {
      const finalState: BranchState = b.progress?.state ?? "done";
      const state: BranchState =
        stage === "done" && finalState === "failed" ? "failed" : stage;
      const elapsed =
        stage === "creating"
          ? 0
          : stage === "running"
            ? 3.3
            : (b.progress?.elapsed_seconds ?? 6.8);
      return { ...b, branch: true, progress: { state, elapsed_seconds: elapsed } };
    });
    frames.push({
      fixture: frame([...rail, ...laneNodes], parentId, null, 1 + n, t, rv),
      caption,
    });
  }

  // 4 — verdict: the winner is promoted to head, losers released.
  const winnerIdx =
    typeof fin.verdict?.winner === "number" ? fin.verdict.winner : 0;
  const promoted = branches[winnerIdx]?.id ?? branches[0].id;
  const settled = branches.map((b, i) => ({
    ...b,
    branch: true,
    state: i === winnerIdx ? "live" : "released",
    progress: b.progress ?? { state: "done" as BranchState, elapsed_seconds: 6.8 },
  }));
  t += 2.0;
  frames.push({
    fixture: frame([...rail, ...settled], promoted, fin.verdict ?? null, 1, t, rv),
    caption: "Keep the branch that passed. Delete the rest. Continue from there.",
  });

  return frames;
}
