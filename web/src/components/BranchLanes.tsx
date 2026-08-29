import type { RailNode } from "../types";

// FR-009-01 / FR-006-02 + FR-006-05 — fan-out branches as parallel lanes under a
// "Branches from <parent-id>" caption, each with its runtime sandbox id, a
// running-state word, and elapsed time.
export function BranchLanes({
  branches,
  head,
  selected,
  onSelect,
}: {
  branches: RailNode[];
  head: string;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const parentId = branches.length ? branches[0].parent : null;

  return (
    <>
      <h2>
        {branches.length ? (
          <>
            Branches{" "}
            <span className="pid">
              from <span className="mono">{parentId}</span>
            </span>
          </>
        ) : (
          "Branches"
        )}
      </h2>
      <div className="lanes">
        {branches.map((n, i) => {
          const released = n.state === "released";
          const st = n.progress?.state ?? n.terminal ?? n.state ?? "done";
          const promoted = n.id === head;
          const laneCls = released
            ? "killed"
            : promoted
              ? "won"
              : "running";
          const tagCls = released ? "killed" : promoted ? "won" : st;
          const tag = released ? "released" : promoted ? "promoted" : st;
          const el =
            typeof n.progress?.elapsed_seconds === "number"
              ? n.progress.elapsed_seconds.toFixed(2) + "s"
              : "";
          return (
            <div
              key={n.id}
              className={`lane ${laneCls} ${n.id === selected ? "sel" : ""}`}
              onClick={() => onSelect(n.id)}
            >
              <div className="laneTop">
                <b>Branch {i}</b>
                <span className={`tag ${tagCls}`}>
                  {tag}
                  {el ? ` · ${el}` : ""}
                </span>
              </div>
              <div className="sbid mono">
                {n.sandbox ?? "(no sandbox)"} · exit {n.exit_code}
              </div>
              <div
                className="cmd mono"
                style={{ marginTop: 6, color: "var(--muted)" }}
              >
                {(n.instruction ?? "").slice(0, 70)}
              </div>
            </div>
          );
        })}
        {branches.length === 0 && (
          <div className="sbid">No branches yet.</div>
        )}
      </div>
    </>
  );
}
