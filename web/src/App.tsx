import { useMemo, useState } from "react";
import { useFixture } from "./useFixture";
import { isBranchNode, type ActionRequest } from "./types";
import { Rail } from "./components/Rail";
import { BranchLanes } from "./components/BranchLanes";
import { VerdictCard } from "./components/VerdictCard";
import { EvidencePanel } from "./components/EvidencePanel";
import { RequestsList } from "./components/RequestsList";
import { Footer } from "./components/Footer";

const NOTICE: Record<string, string> = {
  shipped: "sample data — not a live push (showing the fixture bundled with this deploy)",
  sample: "sample data — endpoint unreachable (showing the built-in example)",
};

export default function App() {
  const { fixture, source } = useFixture();
  const [selected, setSelected] = useState<string | null>(null);
  const [requests, setRequests] = useState<ActionRequest[]>([]);

  const nodes = fixture.nodes ?? [];
  const branches = useMemo(
    () => nodes.filter((n) => isBranchNode(n, nodes)),
    [nodes],
  );
  const railNodes = useMemo(
    () => nodes.filter((n) => !isBranchNode(n, nodes)),
    [nodes],
  );

  // Selection falls back to the head when the selected id leaves the fixture
  // (e.g. a released branch) — spec 006 Edge Cases.
  const effectiveSelected =
    selected && nodes.some((n) => n.id === selected) ? selected : fixture.head;
  const selectedNode = nodes.find((n) => n.id === effectiveSelected);

  function recordRequest(kind: ActionRequest["kind"]) {
    if (!effectiveSelected) return;
    const req: ActionRequest = {
      kind,
      checkpoint_id: effectiveSelected,
      requested_at: new Date().toISOString(),
    };
    // eslint-disable-next-line no-console
    console.log("rewind console request:", JSON.stringify(req));
    setRequests((prev) => [req, ...prev]);
  }

  return (
    <>
      <h1>Rewind</h1>
      <div className="sub">
        Every checkpoint is a snapshot, so any moment in the run is a branch
        point.
      </div>
      {source !== "live" && <div className="notice">{NOTICE[source]}</div>}

      <div className="grid">
        <section>
          <h2>Checkpoints</h2>
          <Rail
            nodes={railNodes}
            head={fixture.head}
            selected={effectiveSelected}
            onSelect={setSelected}
          />
        </section>

        <section>
          <BranchLanes
            branches={branches}
            head={fixture.head}
            selected={effectiveSelected}
            onSelect={setSelected}
          />
          <VerdictCard verdict={fixture.verdict ?? null} />

          <h2>Evidence</h2>
          <RequestsList
            selected={effectiveSelected}
            requests={requests}
            onRequest={recordRequest}
          />
          <EvidencePanel node={selectedNode} />
        </section>
      </div>

      <Footer
        liveSandboxes={fixture.live_sandboxes ?? 0}
        checkpoints={nodes.length}
        branches={branches.length}
        sessionElapsed={fixture.session_elapsed ?? 0}
        runtimeVersion={fixture.runtime_version ?? "—"}
      />
    </>
  );
}
