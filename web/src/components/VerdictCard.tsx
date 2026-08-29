import type { Verdict } from "../types";

// FR-009-01 / Article X — the promoted branch and the one-line reason, marked as
// judged on execution evidence. Nothing rendered when the fixture has no verdict.
export function VerdictCard({ verdict }: { verdict: Verdict | null | undefined }) {
  if (!verdict) return null;
  return (
    <div className="verdict">
      <b>Verdict</b>
      <div style={{ marginTop: 5 }}>{verdict.reason}</div>
      <div className="who">
        judged on execution evidence ·{" "}
        <span className="mono">{verdict.provider ?? ""}</span>
      </div>
    </div>
  );
}
