import { chromium, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import assert from "node:assert/strict";
const output = new URL("../screenshots/casework/", import.meta.url).pathname;
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const nav = () => page.getByRole("navigation", { name: "Case navigation" });
async function enter() {
  await page.goto(
    new URL(
      "dashboard.html?mode=demo",
      process.env.PARAKH_URL || "http://127.0.0.1:5173",
    ).href,
  );
  await page.getByRole("button", { name: "Use bundled demo evidence" }).click();
  await page.getByRole("button", { name: "Open sample analysis" }).click();
  await page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
}
try {
  for (const width of [375, 768, 1280, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    await enter();
    await expect(
      page.getByRole("dialog", { name: "Source receipt" }),
    ).not.toBeVisible();
    for (const view of [
      "Overview",
      "Evidence",
      "Explore",
      "Comms",
      "Money",
      "Authenticity",
      "Graph",
      "Map",
      "Timeline",
      "Findings",
      "Reports",
    ]) {
      if (width <= 650)
        await page
          .getByRole("button", { name: "Toggle navigation", exact: true })
          .click();
      await nav()
        .getByRole("button", { name: new RegExp(`^\\d+ ${view}$`) })
        .click();
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${view} page overflow at ${width}`,
      );
      if (
        [1280, 1920].includes(width) &&
        ["Overview", "Money", "Authenticity", "Timeline"].includes(view)
      )
        await page.screenshot({
          path: `${output}${view.toLowerCase()}-${width}.png`,
          fullPage: true,
        });
    }
    console.log(`All 11 views fit ${width}px`);
  }
  await enter();
  await page
    .getByRole("button", { name: "03 · line:4", exact: true })
    .first()
    .click();
  const drawer = page.getByRole("dialog", { name: "Source receipt" });
  await expect(drawer).toContainText("DEMO-UPI-001");
  await expect(drawer).toContainText("09:25:00 IST");
  await expect(drawer).toContainText("0b8759c9");
  await drawer
    .getByRole("button", { name: "Adjacent events", exact: true })
    .click();
  await expect(drawer).toContainText("DEMO-UPI-002");
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await nav().getByRole("button", { name: "02 Evidence", exact: true }).click();
  await page
    .getByRole("button", { name: "Verify all file hashes", exact: true })
    .click();
  await expect(page.getByText("Hash matches", { exact: true })).toHaveCount(15);
  await page.getByRole("button", { name: "Assistant", exact: true }).click();
  await page.getByLabel("Ask about the evidence").fill("What is the password?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "No supporting evidence found",
  );
  assert.deepEqual(errors, []);
  console.log(
    "Passed exact receipts, adjacent events, 15 source hash checks, and assistant refusal.",
  );
} finally {
  await browser.close();
}
