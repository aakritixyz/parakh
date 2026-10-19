import { chromium, expect } from "@playwright/test";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, readdir, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout } from "node:timers";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const folder = await mkdtemp(path.join(tmpdir(), "parakh-smoke-"));
const password = randomBytes(24).toString("hex");
const env = { ...process.env, DATABASE_URL: `sqlite:///${folder}/case.sqlite`, STORAGE_ROOT: `${folder}/vault`, AUDIT_SIGNING_KEY_PATH: `${folder}/audit.pem`, SECRET_KEY: randomBytes(32).toString("hex"), LOCAL_LLM_PROVIDER: "stub", PARAKH_API: "http://127.0.0.1:18180", PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH };
const python = process.env.PARAKH_PYTHON || "python";
for (const args of [["-m", "app.cli", "migrate"], ["-m", "app.cli", "create-admin", "--username", "smoke-investigator", "--password", password]]) {
  const run = spawnSync(python, args, { cwd: `${root}/backend`, env, encoding: "utf8" });
  if (run.status !== 0) throw Error(run.stderr);
}
const backend = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "18180"], { cwd: `${root}/backend`, env, stdio: ["ignore", "pipe", "pipe"] });
const frontend = spawn("npm", ["run", "dev", "--", "--port", "18181", "--strictPort"], { cwd: `${root}/frontend`, env, stdio: ["ignore", "pipe", "pipe"] });
let logs = "";
for (const child of [backend, frontend]) { child.stdout.on("data", (data) => { logs += data; }); child.stderr.on("data", (data) => { logs += data; }); }
const output = `${root}/docs/validation`;
await mkdir(output, { recursive: true });
let browser;
const steps = [];
try {
  for (const url of ["http://127.0.0.1:18180/health", "http://127.0.0.1:18181/signin.html"]) {
    let ready = false;
    for (let i = 0; i < 120; i++) {
      try { if ((await globalThis.fetch(url)).ok) { ready = true; break; } } catch { /* server startup */ }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    if (!ready) throw Error(`Service unavailable: ${url}\n${logs}`);
  }
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.setDefaultTimeout(25000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("http://127.0.0.1:18181/signin.html");
  await page.getByLabel("Username", { exact: true }).fill("smoke-investigator");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("heading", { name: "Active Cases", exact: true }).waitFor(); steps.push("sign-in");
  await page.getByRole("button", { name: "New case", exact: true }).click();
  await page.getByLabel("Case title", { exact: true }).fill("Riya: investment scam complaint");
  await page.getByLabel("FIR / case number", { exact: true }).fill("SYN-SMOKE-001");
  await page.getByLabel("Police station / jurisdiction", { exact: true }).fill("Synthetic demo");
  await page.getByRole("button", { name: "Create case", exact: true }).click();
  await page.getByRole("button", { name: "Upload evidence", exact: true }).click(); steps.push("create-case");
  await page.getByLabel("Owner", { exact: true }).fill("Riya");
  await page.getByLabel("Who handed it over", { exact: true }).fill("Synthetic Riya");
  await page.getByLabel("Acquisition method", { exact: true }).fill("Synthetic logical exports");
  const evidence = (await readdir(`${root}/evidence`)).sort().map((name) => `${root}/evidence/${name}`);
  await page.getByLabel("Choose evidence files", { exact: true }).setInputFiles(evidence);
  await page.getByRole("button", { name: "Start import", exact: true }).click();
  await page.getByRole("button", { name: "Review import report", exact: true }).click({ timeout: 120000 });
  await page.getByRole("button", { name: "Confirm and continue", exact: true }).click(); steps.push("upload-15-synthetic-files");
  const nav = page.getByRole("navigation", { name: "Case navigation" });
  const go = async (view) => nav.getByRole("button", { name: new RegExp(`^\\d+ ${view}$`) }).click();
  await go("Explore"); await expect(page.getByRole("heading", { name: "Event table", exact: true })).toBeVisible(); steps.push("explore");
  await go("Money"); await page.getByRole("heading", { name: /Normalised|Normalized|transaction/i }).first().waitFor(); steps.push("money");
  await go("Authenticity"); await page.getByRole("heading", { name: /contradiction/i }).first().waitFor(); steps.push("contradiction");
  await go("Timeline"); await page.getByRole("button", { name: "Play replay", exact: true }).click(); await expect(page.getByRole("button", { name: "Pause replay", exact: true })).toBeVisible(); await page.getByRole("button", { name: "Pause replay", exact: true }).click(); steps.push("replay");
  await go("Findings");
  await page.getByLabel("Finding statement", { exact: true }).fill("The cited bank row records Riya's payment; review the source before drawing conclusions.");
  const records = page.getByLabel("Supporting record", { exact: true });
  const options = await records.locator("option").evaluateAll((nodes) => nodes.map((node) => ({ value: node.value, text: node.textContent })));
  await records.selectOption(options.find((option) => option.text.includes("03_bank_statement_riya.csv"))?.value ?? options[1].value);
  await page.getByRole("button", { name: "Add finding", exact: true }).click();
  await page.getByRole("button", { name: "Add to tray", exact: true }).click();
  await page.getByRole("button", { name: "Save findings and tray", exact: true }).click();
  await expect(page.getByRole("status").last()).toContainText("Review saved");
  await go("Reports");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download cited report PDF", exact: true }).click();
  await (await download).saveAs(`${output}/smoke-report.pdf`); steps.push("report-pdf");
  await page.screenshot({ path: `${output}/reports-smoke.png`, fullPage: true });
  if (errors.length) throw Error(errors.join("\n"));
  await writeFile(`${output}/smoke.json`, JSON.stringify({ status: "passed", steps, synthetic_only: true, browser: browser.version() }, null, 2));
  console.log(`PASS: ${steps.join(" -> ")}`);
} catch (error) {
  await writeFile(`${output}/smoke.json`, JSON.stringify({ status: "failed", steps, error: String(error), synthetic_only: true }, null, 2));
  console.error(logs.slice(-6000)); throw error;
} finally {
  await browser?.close(); backend.kill(); frontend.kill();
}
