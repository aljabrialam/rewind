// Spec 009 — a mirror of `Engine.console_fixture()` output (spec 006). Transport
// and render only; this adds no fields to the Console Fixture shape.

export type BranchState = "creating" | "running" | "done" | "failed";

export type BranchProgress = {
  state: BranchState;
  elapsed_seconds: number;
};

export type RailNode = {
  id: string;
  index: number;
  instruction: string;
  parent: string | null;
  children: string[];
  sandbox: string | null;
  state: string;
  snapshot: string | null;
  created_at: string;
  exit_code: number | null;
  stdout: string;
  outcome: string;
  terminal: string | null;
  rationale: string;
  // spec 006 enrichment — branch nodes only
  branch?: boolean;
  progress?: BranchProgress;
};

export type Verdict = {
  winner?: number;
  reason: string;
  provider?: string;
  [k: string]: unknown;
};

export type ConsoleFixture = {
  head: string;
  live_sandboxes?: number;
  session_elapsed?: number;
  runtime_version?: string;
  verdict?: Verdict | null;
  nodes: RailNode[];
};

// Where the on-screen fixture came from (data-model.md §4).
export type FixtureSource = "live" | "shipped" | "sample";

export type ActionRequest = {
  kind: "restore" | "fan_out";
  checkpoint_id: string;
  requested_at: string;
};

// --- helpers shared by the renderer -----------------------------------------

/** A node is a fan-out branch if it says so, or (fallback) its parent has >1 child. */
export function isBranchNode(n: RailNode, all: RailNode[]): boolean {
  if (n.branch === true) return true;
  if (n.parent == null) return false;
  const siblings = all.filter((x) => x.parent === n.parent);
  return siblings.length > 1 && siblings.every((s) => s.children.length === 0);
}

/** Structural check the client applies to any fetched body before it replaces a good view. */
export function looksLikeFixture(v: unknown): v is ConsoleFixture {
  if (typeof v !== "object" || v === null) return false;
  const o = v as Record<string, unknown>;
  if (typeof o.head !== "string") return false;
  if (!Array.isArray(o.nodes)) return false;
  return o.nodes.every(
    (n) =>
      typeof n === "object" &&
      n !== null &&
      typeof (n as Record<string, unknown>).id === "string" &&
      typeof (n as Record<string, unknown>).index === "number",
  );
}
