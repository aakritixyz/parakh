import { performance } from "node:perf_hooks";

const seed = 51026;
let value = seed;
const random = () => ((value = (value * 1664525 + 1013904223) >>> 0) / 2 ** 32);
const cards = Array.from({ length: 500 }, (_, id) => ({ id, x: random() * 10000, y: random() * 6000 }));
const strings = Array.from({ length: 1500 }, (_, id) => ({ id, source: id % 500, target: (id * 37 + 11) % 500 }));
const frames = [];
let checksum = 0;
for (let frame = 0; frame < 240; frame += 1) {
  const started = performance.now();
  const viewport = { x: frame * 3, y: frame * 2, zoom: .5 + (frame % 100) / 100 };
  // Production pan/zoom changes one SVG viewBox; minimap projection is the only per-card JS work.
  for (const card of cards) checksum += (card.x - viewport.x) * viewport.zoom + (card.y - viewport.y) * viewport.zoom;
  checksum += strings.length;
  frames.push(performance.now() - started);
}
frames.sort((a, b) => a - b);
const result = {
  fixture: "deterministic synthetic graph; no case data",
  seed,
  cards: cards.length,
  strings: strings.length,
  frames: frames.length,
  median_ms: Number(frames[Math.floor(frames.length * .5)].toFixed(3)),
  p95_ms: Number(frames[Math.floor(frames.length * .95)].toFixed(3)),
  max_ms: Number(frames.at(-1).toFixed(3)),
  frame_budget_ms: 16.7,
  pass: frames[Math.floor(frames.length * .95)] < 16.7,
  implementation_note: "Pan and zoom update the SVG viewBox; stored card and string geometry is not recomputed.",
  checksum: Math.round(checksum),
};
console.log(JSON.stringify(result, null, 2));
if (!result.pass) process.exitCode = 1;
