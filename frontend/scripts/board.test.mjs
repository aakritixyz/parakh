import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/components/board/boardModel.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2021 } }).outputText;
const { riyaBoard, cloneBoard, deleteBoardCards, BOARD_WARNING } = await import("data:text/javascript;base64," + Buffer.from(code).toString("base64"));

test("Riya answer-key items and receipt-backed path are pinned", () => {
  const board = riyaBoard();
  for (const id of ["riya", "arjun", "handle", "riya-account", "collection", "cashout-one", "cashout-two", "refund", "guarantee"])
    assert(board.cards.some((card) => card.id === id), id);
  assert(board.cards.filter((card) => card.kind !== "note").every((card) => card.receipt));
  assert.match(BOARD_WARNING, /does not prove involvement/i);
  assert.deepEqual(
    ["l-riya-account", "l-riya-payment1", "l-payment1-collection", "l-collection-one"].map((id) => board.links.find((link) => link.id === id)?.status),
    ["established", "established", "established", "established"],
  );
});

test("unsupported strings and identity uncertainty cannot masquerade as established", () => {
  const board = riyaBoard();
  assert.equal(board.links.find((link) => link.id === "l-unsupported").status, "not_established");
  assert.equal(board.links.find((link) => link.id === "l-arjun-handle").status, "possible");
  assert.equal(board.cards.find((card) => card.id === "arjun").community, board.cards.find((card) => card.id === "arjun-phone").community);
});

test("snapshot cloning retains identical seed, layout and locked positions", () => {
  const board = riyaBoard(), snapshot = cloneBoard(board);
  assert.notEqual(snapshot, board);
  assert.deepEqual(snapshot, board);
  assert.equal(snapshot.seed, 51026);
  assert(snapshot.cards.find((card) => card.id === "riya").locked);
});

test("undo restores a deleted card and all of its strings", () => {
  const before = riyaBoard(), afterDelete = deleteBoardCards(before, ["collection"]);
  assert(!afterDelete.cards.some((card) => card.id === "collection"));
  assert(!afterDelete.links.some((link) => link.source === "collection" || link.target === "collection"));
  const afterUndo = cloneBoard(before);
  assert.deepEqual(afterUndo, before);
  assert(afterUndo.cards.some((card) => card.id === "collection"));
});
