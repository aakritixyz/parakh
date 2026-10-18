import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import test from "node:test";
import ts from "typescript";
const fixture = JSON.parse(
  await readFile(
    new URL("../src/components/casework/demo.json", import.meta.url),
    "utf8",
  ),
);
const source = await readFile(
  new URL("../src/components/casework/model.ts", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(
  source.replace(
    'import fixture from "./demo.json";',
    `const fixture=${JSON.stringify(fixture)};`,
  ),
  {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2021,
    },
  },
).outputText;
const { verifyChain, findings } = await import(
  "data:text/javascript;base64," + Buffer.from(code).toString("base64")
);
test("all source hashes match the original 15 synthetic files and all parser references resolve", async () => {
  assert.equal(fixture.files.length, 15);
  for (const file of fixture.files) {
    const bytes = await readFile(
      new URL("../../evidence/" + file.file, import.meta.url),
    );
    assert.equal(createHash("sha256").update(bytes).digest("hex"), file.sha256);
    const records = fixture.events.filter((e) => e.evidence_id === file.id);
    assert.equal(records.length, file.records);
    for (const event of records)
      assert(
        file.rows.some((r) => r.ref === event.raw_ref),
        `${event.file} ${event.raw_ref}`,
      );
  }
});
test("curated findings point to actual source records and preserve uncertainty", () => {
  for (const finding of findings)
    for (const c of finding.citations) {
      const f = fixture.files.find((f) => f.id === c.file);
      assert(f);
      assert(
        f.rows.some((r) => r.ref === c.ref),
        `${finding.id} ${c.file} ${c.ref}`,
      );
    }
  assert.match(findings[1].answer, /arjun.collect@demo/);
  assert.equal(findings[4].status, "Possible");
  assert.equal(findings[5].status, "Not established");
  assert.match(findings[6].limits, /excerpt/);
});
test("demo chain verifies but tampered payloads and broken links fail", async () => {
  assert.equal(await verifyChain(fixture.audit), true);
  const altered = globalThis.structuredClone(fixture.audit);
  altered[4].sha256 = "f".repeat(64);
  assert.equal(await verifyChain(altered), false);
  const broken = globalThis.structuredClone(fixture.audit);
  broken[5].previous_hash = "0".repeat(64);
  assert.equal(await verifyChain(broken), false);
  assert.equal(await verifyChain([]), false);
});
