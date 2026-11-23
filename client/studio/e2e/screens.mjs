// W15.1: screenshots of the editor for the README and the visual review: 1440x900 and 1280x720, light and dark; nothing selected, a scene
// selected, and the assistant mid-conversation (a scripted stand-in for Claude Code, as in assistant-agent.mjs).
//   VT_URL=http://localhost:5174 VT_PROJECT=c6-shot VT_OUT=<folder> node e2e/screens.mjs
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c6-shot", out = process.env.VT_OUT || "screens";
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const shots = [];
for (const [w, h] of [[1440, 900], [1280, 720]]) {
  for (const theme of ["light", "dark"]) {
    const page = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage();
    await page.addInitScript((t) => {
      try { localStorage.setItem("vt-theme", t); } catch {}
      const listeners = new Set();
      const emit = (event) => setTimeout(() => listeners.forEach((cb) => cb({ conversationId: "c1", event })), 40);
      window.vtDesktop = { agents: {
        status: async () => ({ found: true, logged_in: true, version: "2", reason: "", adapter: true }),
        list: async () => [],
        open: async () => ({ conversationId: "c1", resumed: false, note: "" }),
        send: async () => {
          emit({ type: "step", id: "a", title: "Get scenes", status: "completed" });
          emit({ type: "step", id: "b", title: "Write shot", status: "completed" });
          emit({ type: "step", id: "c", title: "Get shot frame", status: "in_progress" });
          emit({ type: "text", text: "I drew [scene 2](vt://scene/s2) as a shot: a battery that drains from green to red, with the word Battery above it. Looking at one frame now." });
          return { ok: true };
        },
        stop: async () => {}, permission: async () => {}, signIn: async () => {},
        onEvent: (cb) => { listeners.add(cb); return () => listeners.delete(cb); },
      } };
    }, theme);
    await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
    await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
    await page.waitForTimeout(2500);
    const name = (state) => path.join(out, `editor-${w}x${h}-${theme}-${state}.png`);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await page.screenshot({ path: name("none") }); shots.push(name("none"));
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: "s2" })));
    await page.waitForTimeout(1200);
    await page.screenshot({ path: name("scene") }); shots.push(name("scene"));
    await page.getByRole("tab", { name: "Claude Code" }).click();
    const box = page.getByLabel("Message to Claude Code");
    await box.waitFor({ timeout: 10000 });
    await box.fill("Draw scene 2 as a shot: a phone battery draining from green to red.");
    await page.keyboard.press("Enter");
    await page.getByText("Looking at one frame now.").waitFor({ timeout: 10000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: name("assistant") }); shots.push(name("assistant"));
    await page.close();
  }
}
await browser.close();
console.log(shots.join("\n"));
