import { isBranchNode, type BranchState, type ConsoleFixture, type RailNode } from "./types";

// Spec 009 — the Replay button. Pure client-side: it takes the current fixture
// (the last real run pushed to the console, or the bundled one) and derives a
// short sequence of frames that replays the run's shape through the same
// components — seed steps filling in, a step failing, the head jumping back,
// three branches fanning out, then the verdict. No engine, no network.

export const REPLAY_FRAME_MS = 1500;
export const REPLAY_HOLD_MS = 2600; // linger on the final frame before releasing

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
export function buildReplayFrames(fin: ConsoleFixture): ConsoleFixture[] {
  const all = fin.nodes ?? [];
  if (all.length === 0) return [fin];

  const rail = all.filter((n) => !isBranchNode(n, all));
  const branches = all.filter((n) => isBranchNode(n, all));
  const rv = fin.runtime_version;
  const frames: ConsoleFixture[] = [];
  let t = 0;

  // 1 — seed steps appear one by one; head follows the newest.
  for (let i = 1; i <= rail.length; i++) {
    const shown = rail.slice(0, i);
    t += 3.1;
    frames.push(frame(shown, shown[shown.length - 1].id, null, 1, t, rv));
  }

  if (branches.length === 0) {
    frames.push(frame(rail, fin.head, fin.verdict ?? null, fin.live_sandboxes ?? 0, t, rv));
    return frames;
  }

  // 2 — rewind: the head jumps back to the last good checkpoint (the branch
  //     parent), the failing tail still visible on the rail.
  const parentId =
    branches[0].parent ??
    rail[Math.max(0, rail.length - 3)]?.id ??
    fin.head;
  t += 1.4;
  frames.push(frame(rail, parentId, null, 1, t, rv));

  // 3 — fan-out: three branches, cycling creating -> running -> done.
  const stages: BranchState[] = ["creating", "running", "done"];
  for (const stage of stages) {
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
    frames.push(
      frame([...rail, ...laneNodes], parentId, null, 1 + branches.length, t, rv),
    );
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
  frames.push(
    frame([...rail, ...settled], promoted, fin.verdict ?? null, 1, t, rv),
  );

  return frames;
}
