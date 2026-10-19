import { readFile, readdir } from "node:fs/promises";
import assert from "node:assert/strict";
const root = new URL("../src/", import.meta.url);
const files = await readdir(root, { recursive: true });
for (const file of files.filter(
  (file) => /\.(css|tsx?)$/.test(file) && file.replaceAll("\\", "/") !== "styles/tokens.css",
)) {
  const source = await readFile(new URL(file, root), "utf8");
  assert(
    !/#[0-9a-f]{3,8}\b|\brgba?\(|\bhsla?\(/i.test(source),
    `Color outside tokens: ${file}`,
  );
  assert(!/gradient\(/i.test(source), `Gradient in ${file}`);
}
const tokens = await readFile(new URL("styles/tokens.css", root), "utf8");
const token = (name) =>
  tokens.match(new RegExp(`--${name}:\\s*(#[a-f0-9]{6})`, "i"))[1];
function luminance(hex) {
  const channels = hex
    .slice(1)
    .match(/../g)
    .map((value) => parseInt(value, 16) / 255)
    .map((value) =>
      value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
    );
  return channels.reduce(
    (sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i],
    0,
  );
}
for (const bg of ["surface", "bg"]) {
  const values = [luminance(token("ink-3")), luminance(token(bg))].sort(
    (a, b) => a - b,
  );
  const contrast = (values[1] + 0.05) / (values[0] + 0.05);
  assert(contrast >= 4.5, `Muted text fails AA on ${bg}: ${contrast}`);
  console.log(`Muted text on ${bg}: ${contrast.toFixed(2)}:1 (AA)`);
}
console.log("All source colors use tokens; no gradients.");
