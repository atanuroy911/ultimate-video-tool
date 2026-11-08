import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const base = process.env.VT_URL || "http://127.0.0.1:5174";
const project = { id: "qa-video", title: "QA video", duration: 125, audio_url: "/media/qa-video/input.mp4" };
const highlights = [
  { title: "First moment", start_time: 4, end_time: 34, score: 92, hook_sentence: "First hook", virality_reason: "Clear opening" },
  { title: "Second moment", start_time: 50, end_time: 82, score: 85, hook_sentence: "Second hook", virality_reason: "Useful payoff" },
];
await page.route("**/api/**", async route => {
  const path = new URL(route.request().url()).pathname;
  const body = path === "/api/projects" ? [project]
    : path === "/api/projects/qa-video/shorts" ? { highlights, preview_url: "/media/qa-video/input.mp4" }
    : path === "/api/health" ? { ok: true, api_version: 8 }
    : path === "/api/settings" ? {}
    : path === "/api/ai/status" ? { provider: "off", available: false, model: "" }
    : {};
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
});
try {
  await page.goto(`${base}/p/qa-video/shorts`);
  try { await page.getByText(/^Moment 1 of 2/).waitFor({ timeout: 5000 }); }
  catch (error) { console.error((await page.locator("body").innerText()).slice(0, 2500)); throw error; }
  if (!(await page.locator("video[src='/media/qa-video/input.mp4']").count())) throw new Error("Source video preview missing");
  await page.getByRole("button", { name: "Next moment" }).click();
  await page.getByText(/^Moment 2 of 2/).waitFor();
  await page.getByRole("checkbox", { name: "Keep Second moment" }).uncheck();
  await page.getByRole("heading", { name: "1 moment selected" }).waitFor({ timeout: 3000 }).catch(() => { throw new Error("Batch selection did not change"); });
  await page.getByRole("button", { name: "Previous moment" }).click();
  await page.getByText(/^Moment 1 of 2/).waitFor();
  await page.getByRole("button", { name: "Change video" }).click();
  if (!(await page.getByRole("button", { name: "Upload", exact: true }).count())) throw new Error("Direct upload missing");
  console.log("Shorts upload, video preview, next/previous moment and batch selection controls passed");
} finally {
  await browser.close();
}
