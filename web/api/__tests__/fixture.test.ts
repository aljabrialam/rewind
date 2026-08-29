import { describe, it, expect } from "vitest";
import {
  handleRequest,
  isWellFormedFixture,
  MAX_BODY_BYTES,
  type CoreRequest,
  type FixtureStore,
} from "../fixture";

const TOKEN = "s3cr3t-demo-token";

const VALID_FIXTURE = {
  head: "b1",
  live_sandboxes: 2,
  session_elapsed: 12.5,
  runtime_version: "v0.207.0",
  verdict: { winner: 0, reason: "b1 exited 0", provider: "deterministic-fallback" },
  nodes: [
    { id: "root", index: 0, instruction: "(start)", parent: null, children: ["b1"], sandbox: "sb0", state: "live", snapshot: null, created_at: "", exit_code: 0, stdout: "", outcome: "ok", terminal: null, rationale: "" },
    { id: "b1", index: 1, instruction: "echo hi", parent: "root", children: [], sandbox: "sb1", state: "live", snapshot: null, created_at: "", exit_code: 0, stdout: "hi\n", outcome: "ok", terminal: "done", rationale: "", branch: true, progress: { state: "done", elapsed_seconds: 1.2 } },
  ],
};

type TestStore = FixtureStore & { _value: string | null };

function makeStore(over: Partial<FixtureStore> = {}): TestStore {
  const s: TestStore = {
    _value: null,
    token: TOKEN,
    writable: true,
    get(): Promise<string | null> {
      return Promise.resolve(s._value);
    },
    put(body: string): Promise<void> {
      s._value = body;
      return Promise.resolve();
    },
  };
  Object.assign(s, over);
  return s;
}

function req(method: string, opts: Partial<CoreRequest> = {}): CoreRequest {
  const headers: Record<string, string> = {};
  return {
    method,
    header: (n) => headers[n.toLowerCase()],
    rawBody: "",
    ...opts,
  };
}

function withToken(token: string, body: string, method = "POST"): CoreRequest {
  return {
    method,
    header: (n) => (n.toLowerCase() === "x-rewind-token" ? token : undefined),
    rawBody: body,
  };
}

describe("isWellFormedFixture", () => {
  it("accepts a full fixture and the leaner FAKE=1 shape", () => {
    expect(isWellFormedFixture(VALID_FIXTURE)).toBe(true);
    expect(
      isWellFormedFixture({ head: "root", nodes: [{ id: "root", index: 0 }] }),
    ).toBe(true);
  });
  it("rejects non-objects, missing head, non-array nodes, bad node ids", () => {
    expect(isWellFormedFixture(null)).toBe(false);
    expect(isWellFormedFixture([])).toBe(false);
    expect(isWellFormedFixture({ nodes: [] })).toBe(false);
    expect(isWellFormedFixture({ head: "x", nodes: {} })).toBe(false);
    expect(isWellFormedFixture({ head: "x", nodes: [{ index: 0 }] })).toBe(false);
    expect(isWellFormedFixture({ head: "x", nodes: [{ id: "a" }] })).toBe(false);
  });
  it("rejects wrong types on optional fields", () => {
    expect(isWellFormedFixture({ head: "x", nodes: [], live_sandboxes: "2" })).toBe(false);
    expect(isWellFormedFixture({ head: "x", nodes: [], verdict: 3 })).toBe(false);
  });
});

describe("GET /api/fixture", () => {
  it("get_empty_store_returns_bundled", async () => {
    const store = makeStore();
    const res = await handleRequest(req("GET"), store);
    expect(res.status).toBe(200);
    expect(res.headers["cache-control"]).toBe("no-store");
    const body = JSON.parse(res.body);
    expect(isWellFormedFixture(body)).toBe(true); // the bundled public/tree.json
  });

  it("valid_post_is_served_by_next_get", async () => {
    const store = makeStore();
    const post = await handleRequest(
      withToken(TOKEN, JSON.stringify(VALID_FIXTURE)),
      store,
    );
    expect(post.status).toBe(200);
    const get = await handleRequest(req("GET"), store);
    expect(JSON.parse(get.body).head).toBe("b1");
  });
});

describe("POST /api/fixture — rejections leave the served fixture unchanged", () => {
  it("missing_token_401_no_change", async () => {
    const store = makeStore();
    store._value = JSON.stringify(VALID_FIXTURE);
    const res = await handleRequest(req("POST", { rawBody: JSON.stringify(VALID_FIXTURE) }), store);
    expect(res.status).toBe(401);
    expect(JSON.parse((await handleRequest(req("GET"), store)).body).head).toBe("b1");
  });

  it("wrong_token_401_no_change", async () => {
    const store = makeStore();
    store._value = JSON.stringify({ ...VALID_FIXTURE, head: "keep" });
    const res = await handleRequest(withToken("nope", JSON.stringify(VALID_FIXTURE)), store);
    expect(res.status).toBe(401);
    expect(JSON.parse((await handleRequest(req("GET"), store)).body).head).toBe("keep");
  });

  it("malformed_body_422_no_change", async () => {
    const store = makeStore();
    store._value = JSON.stringify({ ...VALID_FIXTURE, head: "keep" });

    const notJson = await handleRequest(withToken(TOKEN, "{ not json"), store);
    expect(notJson.status).toBe(422);

    const notFixture = await handleRequest(withToken(TOKEN, JSON.stringify({ hello: 1 })), store);
    expect(notFixture.status).toBe(422);

    expect(JSON.parse((await handleRequest(req("GET"), store)).body).head).toBe("keep");
  });

  it("oversize_body_413", async () => {
    const store = makeStore();
    const big = JSON.stringify({
      head: "x",
      nodes: [{ id: "x", index: 0, pad: "a".repeat(MAX_BODY_BYTES) }],
    });
    const res = await handleRequest(withToken(TOKEN, big), store);
    expect(res.status).toBe(413);
    // also honours a caller-set tooLarge flag without reading the body
    const flagged = await handleRequest(
      { ...withToken(TOKEN, ""), tooLarge: true },
      store,
    );
    expect(flagged.status).toBe(413);
  });
});

describe("POST /api/fixture — store configuration", () => {
  it("no_store_returns_501_and_get_still_serves_bundled", async () => {
    const store = makeStore({ writable: false });
    const post = await handleRequest(withToken(TOKEN, JSON.stringify(VALID_FIXTURE)), store);
    expect(post.status).toBe(501);
    const get = await handleRequest(req("GET"), store);
    expect(get.status).toBe(200);
    expect(isWellFormedFixture(JSON.parse(get.body))).toBe(true);
  });
});

describe("other methods", () => {
  it("method_not_allowed_405", async () => {
    const store = makeStore();
    const res = await handleRequest(req("DELETE"), store);
    expect(res.status).toBe(405);
    expect(res.headers.allow).toBe("GET, POST");
  });
});
