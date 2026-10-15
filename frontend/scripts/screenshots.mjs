import { chromium, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import assert from "node:assert/strict";
const output = new URL("../screenshots/", import.meta.url).pathname;
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
// Stable offline fixture exercises the existing demo fallback without depending on a running backend.
await page.route("**/api/**", (route) =>
  route.fulfill({ status: 503, body: "{}" }),
);
try {
  for (const width of [1280, 1440, 1600, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(process.env.PARAKH_URL || "http://127.0.0.1:5173");
    await page
      .getByRole("navigation", { name: "Investigation views" })
      .waitFor();
    for (const view of ["Dashboard", "Timeline", "Graph", "Communications"]) {
      const tab = page
        .getByRole("navigation", { name: "Investigation views" })
        .getByRole("button", { name: view, exact: true });
      await tab.click();
      const geometry = await page.evaluate(() => ({
        page: document.documentElement.scrollWidth,
        viewport: innerWidth,
        stage: document.querySelector(".stage").scrollWidth,
        stageWidth: document.querySelector(".stage").clientWidth,
        cards: Array.from(document.querySelectorAll(".metric")).map(
          (el) => el.getBoundingClientRect().width,
        ),
      }));
      assert(
        geometry.page <= geometry.viewport,
        `${view} page overflow at ${width}: ${JSON.stringify(geometry)}`,
      );
      assert(
        geometry.stage <= geometry.stageWidth + 1,
        `${view} content overflow at ${width}: ${JSON.stringify(geometry)}`,
      );
      assert(
        geometry.cards.every((size) => size >= 180),
        `KPI narrower than 180px at ${width}`,
      );
      if (width === 1280 || width === 1920)
        await page.screenshot({
          path: `${output}${view.toLowerCase()}-${width}.png`,
          fullPage: true,
        });
    }
    // Check every remaining screen, including all workspace destinations.
    for (const view of [
      "AI Leads",
      "Map",
      "Gallery",
      "Persons",
      "Emails",
      "Identifiers",
      "Authenticity",
      "Fraud",
      "Reconstruction",
      "Assistant",
    ]) {
      await page
        .getByRole("navigation", { name: "Investigation views" })
        .getByRole("button", { name: view, exact: true })
        .click();
      assert(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <= innerWidth &&
            document.querySelector(".stage").scrollWidth <=
              document.querySelector(".stage").clientWidth + 1,
        ),
        `${view} overflow at ${width}`,
      );
    }
    for (const name of [
      "Inactive Cases",
      "Public Report",
      "Private Report",
      "System Jobs",
      "Identifier Search",
      "Generated Reports",
      "Settings",
    ]) {
      await page
        .getByRole("navigation", { name: "Workspace", exact: true })
        .getByRole("button", { name, exact: true })
        .click();
      assert(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <= innerWidth &&
            document.querySelector(".stage").scrollWidth <=
              document.querySelector(".stage").clientWidth + 1,
        ),
        `${name} overflow at ${width}`,
      );
    }
    await page
      .getByRole("navigation", { name: "Investigation views" })
      .getByRole("button", { name: "Timeline", exact: true })
      .click();
    assert.equal(
      await page.locator(".drawer").count(),
      0,
      "Details must start closed",
    );
    await page.locator(".event-row").first().click();
    await page.locator(".drawer").waitFor();
    if (width < 1440)
      assert(
        await page.locator(".drawer-scrim").isVisible(),
        "Overlay needs a scrim",
      );
    else
      assert(
        await page.evaluate(
          () =>
            document.querySelector(".stage").getBoundingClientRect().right <=
            document.querySelector(".drawer").getBoundingClientRect().left + 1,
        ),
        "Drawer overlaps stage",
      );
    if (width === 1280 || width === 1920)
      await page.screenshot({
        path: `${output}details-${width}.png`,
        fullPage: true,
      });
    await page.keyboard.press("Escape");
    assert.equal(
      await page.locator(".drawer").count(),
      0,
      "Escape closes details",
    );
    console.log(`Passed all screens and drawer at ${width}px`);
  }

  const fixture = {
    evidence: [],
    timeline: Array.from({ length: 1000 }, (_, i) => ({
      event_id: i + 1,
      evidence_id: 1,
      action: "message",
      summary: "Virtual event " + (i + 1),
      timestamp_utc: "2026-09-12T03:40:00Z",
    })),
    graph: { nodes: [], edges: [] },
    fraud: [],
    anomalies: [],
    authenticity: [],
    reconstruction: { phases: [], narrative: "Screenshot fixture", gaps: [] },
  };
  await page.unroute("**/api/**");
  await page.route("**/api/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        route.request().url().includes("/auth/token")
          ? { access_token: "screenshot-fixture" }
          : fixture,
      ),
    }),
  );
  await page.reload();
  await page
    .getByRole("navigation", { name: "Investigation views" })
    .getByRole("button", { name: "Timeline", exact: true })
    .click();
  await expect(page.locator(".result-line")).toContainText("1,000");
  assert(
    (await page.locator(".event-row").count()) < 100,
    "Large list should be virtualized",
  );
  await page.locator(".event-list").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(page.locator(".event-row").last()).toContainText(
    "Virtual event 1000",
  );
  await page.locator(".event-row").last().click();
  await expect(page.locator(".detail-block").first()).toContainText(
    "Virtual event 1000",
  );
  console.log("Passed 1,000-event virtualization and last-event selection");

  assert.deepEqual(errors, [], "Browser runtime errors");
} finally {
  await browser.close();
}
