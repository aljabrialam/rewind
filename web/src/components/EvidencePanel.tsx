import type { RailNode } from "../types";

// FR-009-01 / FR-006-06 + FR-006-08 — exit status and output for the selected
// checkpoint or branch; the agent rationale in a separate labelled area that
// says it is not evidence, and absent entirely when there is none.
export function EvidencePanel({ node }: { node: RailNode | undefined }) {
  return (
    <>
      <div className="exit">
        {node ? (
          <>
            exit code{" "}
            <b className={`${node.exit_code ? "r" : "g"} mono`}>
              {String(node.exit_code)}
            </b>
          </>
        ) : (
          ""
        )}
      </div>
      <pre>
        {node ? node.stdout || "(no output)" : "Select a checkpoint."}
      </pre>
      {node && node.rationale ? (
        <div className="rationale">
          <span className="lbl">agent rationale — not evidence</span>
          {node.rationale}
        </div>
      ) : null}
    </>
  );
}
