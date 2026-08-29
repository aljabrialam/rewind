import type { RailNode } from "../types";

// FR-009-01 / FR-006-01 — every checkpoint in run order, the head marked.
// Branch nodes are excluded here (they render as lanes).
export function Rail({
  nodes,
  head,
  selected,
  onSelect,
}: {
  nodes: RailNode[];
  head: string;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="rail">
      {nodes.map((n) => {
        const failed = n.exit_code !== 0 && n.exit_code !== null;
        const cls = [
          "node",
          failed ? "fail weight failure" : "ok",
          n.id === head ? "head" : "",
          n.id === selected ? "sel" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <div key={n.id} className={cls} onClick={() => onSelect(n.id)}>
            <div className="cmd mono">{(n.instruction ?? "").slice(0, 80)}</div>
            <div className="meta">
              <span className="mono">
                #{n.index} · {n.id} · {n.sandbox ?? ""}
              </span>
              {failed && (
                <>
                  {" · "}
                  <span className="mono" style={{ color: "var(--killed)" }}>
                    exit {n.exit_code}
                  </span>
                </>
              )}
            </div>
          </div>
        );
      })}
      {nodes.length === 0 && <div className="sbid">Waiting for the run.</div>}
    </div>
  );
}
