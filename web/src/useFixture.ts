import { useEffect, useRef, useState } from "react";
import { SAMPLE } from "./sample";
import { looksLikeFixture, type ConsoleFixture, type FixtureSource } from "./types";

// Poll interval: spec 006 uses 2s; allow a client-safe override but never slower.
const POLL_MS = Math.min(
  2000,
  Number((import.meta.env.VITE_POLL_MS as string | undefined) ?? 2000) || 2000,
);

// Resolve both URLs relative to the page location, so a sub-path deploy works
// (contract: "resolve the endpoint relative to its own location").
const ENDPOINT_URL = new URL("api/fixture", document.baseURI).toString();
const SHIPPED_URL = new URL("tree.json", document.baseURI).toString();

async function tryFetch(url: string): Promise<ConsoleFixture | null> {
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) return null;
    const body: unknown = await r.json();
    return looksLikeFixture(body) ? body : null;
  } catch {
    return null;
  }
}

export type FixtureResult = {
  fixture: ConsoleFixture;
  source: FixtureSource;
  /** advances once per completed poll — handy for a "last updated" readout */
  tick: number;
};

/**
 * The console's only data path. Each poll: endpoint -> bundled tree.json ->
 * in-code SAMPLE. A failed or malformed poll keeps the last good fixture and
 * its source (NFR-009-06) — a good view is never replaced by a broken one.
 */
export function useFixture(): FixtureResult {
  const [state, setState] = useState<FixtureResult>({
    fixture: SAMPLE,
    source: "sample",
    tick: 0,
  });
  const last = useRef(state);
  last.current = state;

  useEffect(() => {
    let alive = true;

    async function poll() {
      const live = await tryFetch(ENDPOINT_URL);
      if (!alive) return;
      if (live) {
        setState({ fixture: live, source: "live", tick: last.current.tick + 1 });
        return;
      }
      const shipped = await tryFetch(SHIPPED_URL);
      if (!alive) return;
      if (shipped) {
        setState({
          fixture: shipped,
          source: "shipped",
          tick: last.current.tick + 1,
        });
        return;
      }
      // Both hops failed. Keep the last good fixture if we ever had one;
      // otherwise sit on SAMPLE.
      if (last.current.source === "live" || last.current.source === "shipped") {
        setState({ ...last.current, tick: last.current.tick + 1 });
      } else {
        setState({ fixture: SAMPLE, source: "sample", tick: last.current.tick + 1 });
      }
    }

    poll();
    const id = window.setInterval(poll, POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  return state;
}
