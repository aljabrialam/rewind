// FR-009-01 / FR-006-07 — always-visible session counters. The numbers are
// console-derived (interface face); only the daytona version is runtime-issued
// (mono).
export function Footer({
  liveSandboxes,
  checkpoints,
  branches,
  sessionElapsed,
  runtimeVersion,
}: {
  liveSandboxes: number;
  checkpoints: number;
  branches: number;
  sessionElapsed: number;
  runtimeVersion: string;
}) {
  return (
    <footer>
      <span>
        live sandboxes <b>{liveSandboxes}</b>
      </span>
      <span>
        checkpoints <b>{checkpoints}</b>
      </span>
      <span>
        branches <b>{branches}</b>
      </span>
      <span>
        session <b>{sessionElapsed.toFixed(1)}s</b>
      </span>
      <span style={{ marginLeft: "auto" }}>
        daytona <b className="mono">{runtimeVersion || "—"}</b>
      </span>
    </footer>
  );
}
