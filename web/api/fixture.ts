// Spec 009 — the fixture endpoint. One serverless function, one current fixture.
// GET returns it (stored object -> bundled fixture). POST replaces it, gated by
// a shared-secret header, a size cap, and a structural shape check. Makes NO
// sandbox-runtime or engine call.
//
// See specs/009-deployable-console/contracts/fixture-endpoint.md
//
// The pure core (handleRequest / isWellFormedFixture) is exported for
// web/api/__tests__/fixture.test.ts. Constitution Article VI: this is endpoint
// logic, not UI rendering.

import { timingSafeEqual } from "node:crypto";
import bundled from "../public/tree.json";

export const MAX_BODY_BYTES = 512 * 1024; // 512 KiB (NFR-009-04)
const TOKEN_HEADER = "x-rewind-token";
const STORE_KEY = "fixture/current.json";

// --- shape gate (contract P3 / data-model §2) -------------------------------

export function isWellFormedFixture(v: unknown): boolean {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  if (typeof o.head !== "string") return false;
  if (!Array.isArray(o.nodes)) return false;
  for (const n of o.nodes) {
    if (typeof n !== "object" || n === null) return false;
    const node = n as Record<string, unknown>;
    if (typeof node.id !== "string") return false;
    if (typeof node.index !== "number") return false;
  }
  if ("live_sandboxes" in o && typeof o.live_sandboxes !== "number") return false;
  if ("session_elapsed" in o && typeof o.session_elapsed !== "number") return false;
  if ("verdict" in o && o.verdict !== null && typeof o.verdict !== "object") return false;
  return true;
}

function constantTimeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

// --- storage adapter -------------------------------------------------------

export type FixtureStore = {
  /** the configured secret, or "" when POST is disabled */
  token: string;
  /** true when a write backend is available (contract P5) */
  writable: boolean;
  get(): Promise<string | null>;
  put(body: string): Promise<void>;
};

// --- pure request core ---------------------------------------------------

export type CoreRequest = {
  method: string;
  header(name: string): string | undefined;
  /** raw body bytes as a string; already size-checked by the caller */
  rawBody: string;
  /** true when the caller already rejected the body on Content-Length */
  tooLarge?: boolean;
};

export type CoreResponse = {
  status: number;
  body: string;
  headers: Record<string, string>;
};

const json = (status: number, obj: unknown, extra: Record<string, string> = {}): CoreResponse => ({
  status,
  body: JSON.stringify(obj),
  headers: { "content-type": "application/json", ...extra },
});

export async function handleRequest(
  req: CoreRequest,
  store: FixtureStore,
): Promise<CoreResponse> {
  const method = (req.method || "GET").toUpperCase();

  if (method === "GET") {
    const stored = await store.get();
    const body = stored ?? JSON.stringify(bundled);
    return {
      status: 200,
      body,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    };
  }

  if (method === "POST") {
    if (!store.writable) {
      return json(501, { error: "no write store configured" });
    }
    const supplied = req.header(TOKEN_HEADER) ?? "";
    if (!store.token || !constantTimeEqual(supplied, store.token)) {
      return json(401, { error: "bad or missing token" });
    }
    if (req.tooLarge || Buffer.byteLength(req.rawBody) > MAX_BODY_BYTES) {
      return json(413, { error: "payload too large" });
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(req.rawBody);
    } catch {
      return json(422, { error: "body is not valid JSON" });
    }
    if (!isWellFormedFixture(parsed)) {
      return json(422, { error: "body is not a well-formed console fixture" });
    }
    await store.put(JSON.stringify(parsed));
    return json(200, { ok: true, nodes: (parsed as { nodes: unknown[] }).nodes.length });
  }

  return json(405, { error: "method not allowed" }, { allow: "GET, POST" });
}

// --- real Vercel Node entry --------------------------------------------

async function makeBlobStore(): Promise<FixtureStore> {
  const token = process.env.REWIND_CONSOLE_TOKEN ?? "";
  const blobToken = process.env.BLOB_READ_WRITE_TOKEN ?? "";
  if (!blobToken) {
    return {
      token,
      writable: false,
      async get() {
        return null;
      },
      async put() {
        /* unreachable — writable is false */
      },
    };
  }
  const { put, list } = await import("@vercel/blob");
  return {
    token,
    writable: true,
    async get() {
      try {
        const { blobs } = await list({ prefix: STORE_KEY, token: blobToken });
        const hit = blobs.find((b) => b.pathname === STORE_KEY) ?? blobs[0];
        if (!hit) return null;
        const r = await fetch(hit.url, { cache: "no-store" });
        return r.ok ? await r.text() : null;
      } catch {
        return null;
      }
    },
    async put(body: string) {
      // Cast keeps this tolerant of @vercel/blob version drift between the
      // local types and the deploy runtime (allowOverwrite is newer).
      await put(STORE_KEY, body, {
        access: "public",
        token: blobToken,
        contentType: "application/json",
        addRandomSuffix: false,
        allowOverwrite: true,
      } as unknown as Parameters<typeof put>[2]);
    },
  };
}

async function readRawBody(req: {
  body?: unknown;
  on?: (ev: string, cb: (c?: unknown) => void) => void;
}): Promise<{ raw: string; tooLarge: boolean }> {
  if (typeof req.body === "string") {
    return { raw: req.body, tooLarge: Buffer.byteLength(req.body) > MAX_BODY_BYTES };
  }
  if (req.body && typeof req.body === "object") {
    const raw = JSON.stringify(req.body);
    return { raw, tooLarge: Buffer.byteLength(raw) > MAX_BODY_BYTES };
  }
  if (typeof req.on !== "function") return { raw: "", tooLarge: false };
  return await new Promise((resolve) => {
    const chunks: Buffer[] = [];
    let size = 0;
    let tooLarge = false;
    req.on!("data", (c?: unknown) => {
      const buf = Buffer.from(c as Buffer);
      size += buf.length;
      if (size > MAX_BODY_BYTES) {
        tooLarge = true;
        return;
      }
      chunks.push(buf);
    });
    req.on!("end", () => resolve({ raw: Buffer.concat(chunks).toString("utf8"), tooLarge }));
    req.on!("error", () => resolve({ raw: "", tooLarge }));
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default async function handler(req: any, res: any): Promise<void> {
  const contentLength = Number(req.headers?.["content-length"] ?? 0);
  let raw = "";
  let tooLarge = contentLength > MAX_BODY_BYTES;
  if (!tooLarge && (req.method || "GET").toUpperCase() === "POST") {
    const r = await readRawBody(req);
    raw = r.raw;
    tooLarge = r.tooLarge;
  }

  const store = await makeBlobStore();
  const out = await handleRequest(
    {
      method: req.method || "GET",
      header: (name: string) => {
        const v = req.headers?.[name.toLowerCase()];
        return Array.isArray(v) ? v[0] : v;
      },
      rawBody: raw,
      tooLarge,
    },
    store,
  );

  for (const [k, v] of Object.entries(out.headers)) res.setHeader(k, v);
  res.statusCode = out.status;
  res.end(out.body);
}
