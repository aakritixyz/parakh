import assert from "node:assert/strict";
import { Buffer, File } from "node:buffer";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Execute the real API module with only Vite's build-time environment replaced.
const source = await readFile(
  new URL("../src/api.ts", import.meta.url),
  "utf8",
);
const code = ts
  .transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2021,
    },
  })
  .outputText.replaceAll("import.meta.env", "({})");
const {
  loadDashboard,
  fallbackDashboard,
  createInvestigation,
  uploadCaseEvidence,
} = await import(
  "data:text/javascript;base64," + Buffer.from(code).toString("base64")
);
const credentials = {
  username: "custom-investigator",
  password: "runtime-only-password",
};
const dashboard = Object.fromEntries(
  Object.entries(fallbackDashboard).filter(([key]) => key !== "online"),
);
const response = (body, status = 200) =>
  new globalThis.Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

test("offline demo does not attempt a login or make network requests", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", () => {
    throw new Error("Network should not run");
  });
  assert.equal(await loadDashboard(), fallbackDashboard);
  assert.equal(fetch.mock.callCount(), 0);
});

test("runtime credentials are sent only to the token endpoint and API uses the returned bearer token", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return response(
      url.endsWith("/auth/token") ? { access_token: "test-token" } : dashboard,
    );
  });
  const result = await loadDashboard(7, credentials);
  assert.equal(result.online, true);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "/api/v1/auth/token");
  assert.equal(calls[0].options.body.get("username"), credentials.username);
  assert.equal(calls[0].options.body.get("password"), credentials.password);
  assert.equal(calls[1].url, "/api/v1/cases/7/dashboard");
  assert.equal(calls[1].options.headers.Authorization, "Bearer test-token");
});

test("invalid credentials surface a sign-in error without pretending to connect", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () =>
    response({}, 401),
  );
  await assert.rejects(
    loadDashboard(1, credentials),
    /Check your username and password/,
  );
  assert.equal(fetch.mock.callCount(), 1);
});

test("a network failure remains visible to the sign-in UI", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    throw new Error("API unavailable");
  });
  await assert.rejects(loadDashboard(1, credentials), /API unavailable/);
});

test("a missing token is rejected before any case request", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => response({}));
  await assert.rejects(
    loadDashboard(1, credentials),
    /invalid sign-in response/,
  );
  assert.equal(fetch.mock.callCount(), 1);
});

test("older backends still load through the existing individual endpoints", async (t) => {
  const endpoints = {
    evidence: [],
    timeline: [],
    graph: { nodes: [], edges: [] },
    fraud: [],
    anomalies: [],
    reconstruction: { phases: [], narrative: "", gaps: [] },
  };
  t.mock.method(globalThis, "fetch", async (url) => {
    if (url.endsWith("/auth/token"))
      return response({ access_token: "test-token" });
    if (url.endsWith("/dashboard")) return response({}, 404);
    return response(endpoints[url.split("/").at(-1)]);
  });
  const result = await loadDashboard(1, credentials);
  assert.equal(result.online, true);
  assert.deepEqual(result.timeline, []);
  assert.deepEqual(result.authenticity, []);
});

test("case creation and multipart evidence upload use the chosen case and in-memory token", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return response(url.endsWith("/cases") ? { id: 42 } : { id: 9 });
  });
  const caseId = await createInvestigation(
    "Investigator test",
    "runtime-token",
  );
  assert.equal(caseId, 42);
  assert.equal(JSON.parse(calls[0].options.body).title, "Investigator test");
  const file = new File(["synthetic evidence"], "source.txt", {
    type: "text/plain",
  });
  await uploadCaseEvidence(caseId, file, "runtime-token", "stable-retry-key");
  assert.equal(calls[1].url, "/api/v1/cases/42/evidence");
  assert.equal(calls[1].options.headers.Authorization, "Bearer runtime-token");
  assert.equal(calls[1].options.headers["Idempotency-Key"], "stable-retry-key");
  assert.equal(calls[1].options.body.get("file").name, "source.txt");
  assert.equal(
    await calls[1].options.body.get("file").text(),
    "synthetic evidence",
  );
  assert.equal(calls[1].options.headers["Content-Type"], undefined);
});

test("failed case creation and oversized uploads surface errors", async (t) => {
  t.mock.method(globalThis, "fetch", async () => response({}, 413));
  await assert.rejects(
    createInvestigation("Test", "token"),
    /Could not create the case/,
  );
  await assert.rejects(
    uploadCaseEvidence(42, new File(["test"], "test.txt"), "token", "key"),
    /exceeds the server upload limit/,
  );
});
