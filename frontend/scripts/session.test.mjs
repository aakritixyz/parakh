import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
const source = await readFile(
  new URL("../src/caseApi.ts", import.meta.url),
  "utf8",
);
let version = 0;
async function client() {
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2021,
    },
  }).outputText;
  return import(
    "data:text/javascript;base64," +
      Buffer.from(code + "\n// test " + version++).toString("base64")
  );
}
const session = (token = "access-one") => ({
  access_token: token,
  expires_in: 900,
  user: { id: 1, username: "demo-investigator", role: "investigator" },
});
const response = (body, status = 200) =>
  new globalThis.Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
test("v2 login uses same-origin HttpOnly-cookie transport and authorizes case requests", async (t) => {
  const api = await client(),
    calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return response(url.endsWith("/login") ? session() : []);
  });
  await api.signIn({
    username: "demo-investigator",
    password: "synthetic-only-password",
  });
  await api.getCases();
  assert.equal(calls[0].url, "/api/v2/auth/login");
  assert.equal(calls[0].options.credentials, "same-origin");
  assert.equal(calls[0].options.body.get("username"), "demo-investigator");
  assert.equal(calls[1].options.headers.Authorization, "Bearer access-one");
});
test("concurrent expired access requests share one rotating refresh request", async (t) => {
  const api = await client();
  let refreshes = 0;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/login")) return response(session());
    if (url.endsWith("/refresh")) {
      refreshes++;
      return response(session("access-two"));
    }
    return options.headers.Authorization === "Bearer access-one"
      ? response({ detail: "expired" }, 401)
      : response([]);
  });
  await api.signIn({
    username: "demo-investigator",
    password: "synthetic-only-password",
  });
  await Promise.all([api.getCases(), api.getCases()]);
  assert.equal(refreshes, 1);
});
test("failed refresh clears the signed-in session instead of falling back to demo", async (t) => {
  const api = await client();
  let value;
  t.mock.method(globalThis, "fetch", async (url) =>
    url.endsWith("/login")
      ? response(session())
      : response({ detail: "Session expired" }, 401),
  );
  api.subscribeSession((s) => {
    value = s;
  });
  await api.signIn({
    username: "demo-investigator",
    password: "synthetic-only-password",
  });
  await assert.rejects(api.getCases(), /Session expired/);
  assert.equal(value, null);
  await assert.rejects(api.getCases(), /Sign in to continue/);
});
test("logout prevents a late refresh from restoring the old session", async (t) => {
  const api = await client();
  let finish;
  t.mock.method(globalThis, "fetch", async (url) => {
    if (url.endsWith("/login")) return response(session());
    if (url.endsWith("/refresh"))
      return new Promise((resolve) => {
        finish = resolve;
      });
    return response({ signed_out: true });
  });
  await api.signIn({
    username: "demo-investigator",
    password: "synthetic-only-password",
  });
  const refreshing = api.refreshSession();
  await api.signOut();
  finish(response(session("late-access")));
  await assert.rejects(refreshing, /Session changed/);
  await assert.rejects(api.getCases(), /Sign in to continue/);
});

test("malformed successful login responses do not create an authenticated session", async (t) => {
  const api = await client();
  t.mock.method(globalThis, "fetch", async () => response({}));
  await assert.rejects(
    api.signIn({
      username: "demo-investigator",
      password: "synthetic-only-password",
    }),
    /Invalid sign-in response/,
  );
  await assert.rejects(api.getCases(), /Sign in to continue/);
});
test("failed server logout reports failure and still clears local access", async (t) => {
  const api = await client();
  t.mock.method(globalThis, "fetch", async (url) =>
    url.endsWith("/login")
      ? response(session())
      : response({ detail: "Revocation unavailable" }, 503),
  );
  await api.signIn({
    username: "demo-investigator",
    password: "synthetic-only-password",
  });
  await assert.rejects(api.signOut(), /Revocation unavailable/);
  await assert.rejects(api.getCases(), /Sign in to continue/);
});
test("evidence intake sends acquisition context and per-file classifications", async (t) => {
  const api = await client();
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith("/login")) return response(session());
    return response({ items: [], duplicate_count: 0 }, 202);
  });
  await api.signIn({
    username: "demo-investigator",
    password: "synthetic-only-password",
  });
  const file = new globalThis.File(["synthetic"], "chat.txt", {
    type: "text/plain",
  });
  await api.importEvidence(7, file, "file-key", {
    sourceType: "whatsapp",
    ownerId: 3,
    deviceId: 4,
    handedOverBy: "Riya",
    acquiredAt: "2026-10-18T10:00:00.000Z",
    acquisitionMethod: "Logical export supplied by owner",
    note: "Synthetic evidence",
  });
  const request = calls[1];
  assert.equal(request.url, "/api/v2/cases/7/intake");
  assert.equal(request.options.headers["Idempotency-Key"], "file-key");
  assert.equal(request.options.body.get("source_type"), "whatsapp");
  assert.equal(request.options.body.get("owner_id"), "3");
  assert.equal(request.options.body.get("device_id"), "4");
  assert.equal(request.options.body.get("handed_over_by"), "Riya");
  assert.equal(request.options.body.get("file").name, "chat.txt");
});
