// Shared helpers for the browser tests. Needs a running Studio (`vt studio`) and Chrome:
// by default the headless Chrome that HyperFrames downloaded, or set VT_CHROME to any Chromium-based browser.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const repo = path.resolve(here, "..", "..");
export const base = process.env.VT_URL || "http://127.0.0.1:8765";

export function chromePath() {
  if (process.env.VT_CHROME) return process.env.VT_CHROME;
  const bin = path.join(repo, "renderer", "node_modules", "hyperframes", "bin", "hyperframes.mjs");
  const out = execFileSync(process.execPath, [bin, "browser", "path"], {
    encoding: "utf8",
    env: { ...process.env, HYPERFRAMES_NO_TELEMETRY: "1", DO_NOT_TRACK: "1" },
  });
  const lines = out.split("\n").map((l) => l.trim()).filter(Boolean);
  return lines[lines.length - 1];
}

/** The New page asks one question per screen. Type a script on the first one and press OK until the last screen ("Make my video") is showing. Returns the Make button. */
export async function walkToReady(page, text, { max = 12 } = {}) {
  await page.locator("textarea[aria-label='Link or script']").fill(text);
  const make = page.getByRole("button", { name: /Make my video|Downloading|Contacting/i }).first();
  for (let i = 0; i < max; i++) {
    if (await make.isVisible().catch(() => false)) return make;
    const ok = page.locator(".tf-nav .btn.primary").first();
    if (!(await ok.count()) || !(await ok.isEnabled())) break;
    await ok.click();
    await page.waitForTimeout(250);
  }
  return make;
}
