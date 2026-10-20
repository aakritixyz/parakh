import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(
  new URL("../src/components/casework/mapLayout.ts", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2021,
  },
}).outputText;
const { fanMarkerOffset, projectMapCoordinates, spreadMapCoordinates } = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);

test("map coordinates are normalized into the visible viewport", () => {
  const projected = projectMapCoordinates([
    { key: "delhi", lat: 28.62, lon: 77.36 },
    { key: "mumbai", lat: 19.076, lon: 72.8777 },
    { key: "invalid", lat: Number.NaN, lon: 0 },
  ]);
  assert.equal(projected.length, 2);
  for (const point of projected) {
    assert(point.x >= 8 && point.x <= 92);
    assert(point.y >= 8 && point.y <= 92);
  }
});

test("a single location is centred rather than disappearing", () => {
  assert.deepEqual(
    projectMapCoordinates([{ key: "only", lat: 51.5072, lon: -0.1276 }]),
    [{ key: "only", lat: 51.5072, lon: -0.1276, x: 50, y: 50 }],
  );
});

test("repeated GPS records remain separately selectable", () => {
  const projected = projectMapCoordinates([
    { key: "one", lat: 28.62, lon: 77.36 },
    { key: "two", lat: 28.62, lon: 77.36 },
    { key: "three", lat: 28.62, lon: 77.36 },
  ]);
  const spread = spreadMapCoordinates(projected);
  assert.equal(new Set(spread.map(({ x, y }) => `${x},${y}`)).size, 3);
  for (const point of spread) {
    assert(point.x >= 8 && point.x <= 92);
    assert(point.y >= 8 && point.y <= 92);
  }
});

test("stacked street-map pins fan into distinct screen positions", () => {
  const offsets = [0, 1, 2, 3].map((index) => fanMarkerOffset(index, 4));
  assert.equal(new Set(offsets.map(({ x, y }) => `${x},${y}`)).size, 4);
  assert.deepEqual(fanMarkerOffset(0, 1), { x: 0, y: 0 });
});
