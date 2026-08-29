import type { ActionRequest } from "../types";

// FR-009-01 / FR-006-03 + FR-006-04 — restore / fan-out controls on a selection.
// Each records an intent to an on-screen list and console.log; the console makes
// NO runtime call of any kind (FR-009-08).
export function RequestsList({
  selected,
  requests,
  onRequest,
}: {
  selected: string | null;
  requests: ActionRequest[];
  onRequest: (kind: ActionRequest["kind"]) => void;
}) {
  return (
    <>
      <div className="controls">
        <button disabled={!selected} onClick={() => onRequest("restore")}>
          Restore to this checkpoint
        </button>
        <button disabled={!selected} onClick={() => onRequest("fan_out")}>
          Fan out from this checkpoint
        </button>
      </div>
      {requests.length > 0 && (
        <div className="reqs">
          <div style={{ marginBottom: 2 }}>
            requests (for the orchestrator — the console makes no runtime call)
          </div>
          {requests.slice(0, 6).map((r, i) => (
            <div className="r" key={`${r.requested_at}-${i}`}>
              <b>{r.kind}</b> → <span className="mono">{r.checkpoint_id}</span> ·{" "}
              {r.requested_at.slice(11, 19)}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
