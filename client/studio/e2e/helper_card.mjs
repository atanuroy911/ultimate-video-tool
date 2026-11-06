// The helper card (Settings, Directors) and the Computers card (Server page) in every state, wide and phone, light and dark (PLAN-PERFECT M8).
// The desktop app's bridge (window.vtDesktop.helper) is stood in for by a script, so no desktop app is needed:
//   cd client/studio && VT_SERVER_URL=http://192.168.123.47:8790 npx vite --port 5174 --strictPort --host 127.0.0.1
//   VT_URL=http://127.0.0.1:5174 node e2e/helper_card.mjs [out dir]
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:5174";
const out = process.argv[2] || "e2e/out/helper";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

const SERVER = "http://192.168.123.47:8790";
const claudeReady = { found: true, logged_in: true, version: "2.1.314 (Claude Code)", reason: "" };
const STATES = {
  running: { running: true, version: "1.0.0", servers: [{ server: SERVER, connected: true, state: "connected", last_error: "" }], assistants: { claude: claudeReady, codex: { found: false, logged_in: false, version: "", reason: "Codex CLI is not installed on this computer." } }, autostart: true, installed: true },
  stopped: { running: false, autostart: true, installed: true },
  trouble: { running: true, version: "1.0.0", servers: [{ server: SERVER, connected: false, state: "waiting", last_error: "The server is not answering." }, { server: "http://10.0.0.7:8790", connected: false, state: "connecting", last_error: "" }],
    assistants: { claude: { found: true, logged_in: false, version: "2.1.314", reason: "Open Claude Code once and log in." }, codex: { found: true, logged_in: true, version: "codex-cli 0.166", reason: "" } }, autostart: false, installed: true },
  source: { running: true, version: "1.0.0", servers: [{ server: SERVER, connected: true, state: "connected", last_error: "" }], assistants: { claude: claudeReady }, autostart: false, installed: false },
};
const ago = (h) => new Date(Date.now() - h * 3600e3).toISOString();
const DIRECTORS = {
  directors: [
    { id: "best", kind: "best", label: "Best available", available: true, note: "" },
    { id: "local", kind: "local", label: "Local AI", available: true, note: "" },
    { id: "claude@aaaa1111", kind: "claude-client", device: "aaaa1111", device_name: "MSI-LAPTOP", label: "Claude on MSI-LAPTOP", available: true, note: "Ready on this device." },
    { id: "codex@aaaa1111", kind: "codex-client", device: "aaaa1111", device_name: "MSI-LAPTOP", label: "Codex on MSI-LAPTOP", available: false, note: "Open Codex on this device and sign in." },
    { id: "claude@bbbb2222", kind: "claude-client", device: "bbbb2222", device_name: "Office Mac", label: "Claude on Office Mac", available: false, last_seen: ago(3), note: "Not connected." },
  ],
  order: [], wait_seconds: 120, director_model: "sonnet", claude_usage_today: { calls: 0, cost_usd: 0, seconds: 0 },
};

// the stand-in for the desktop app's bridge: it answers from window.__helper and records what the page asked
const bridge = () => {
  window.__calls = [];
  const copy = () => JSON.parse(JSON.stringify(window.__helper));
  const note = (name, ...args) => { window.__calls.push([name, ...args]); };
  window.vtDesktop = {
    assistants: { status: async () => [], connect: async () => ({ note: "" }) },
    server: { choose: () => {} },
    helper: {
      status: async () => copy(),
      start: async () => { note("start"); window.__helper.running = true; window.__helper.servers = window.__helper.servers || []; window.__helper.assistants = window.__helper.assistants || {}; return copy(); },
      stop: async () => { note("stop"); window.__helper.running = false; return copy(); },
      refresh: async () => { note("refresh"); return copy(); },
      removeServer: async (a) => { note("removeServer", a); window.__helper.servers = window.__helper.servers.filter((s) => s.server !== a); return copy(); },
      setAutostart: async (on) => { note("setAutostart", on); window.__helper.autostart = on; return copy(); },
    },
  };
};

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const errors = [];
async function open(width, height, scheme, helper, withApp = true) {
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
  await ctx.addInitScript((th) => { try { localStorage.setItem("vt-theme", th); } catch {} }, scheme);
  if (withApp) { await ctx.addInitScript((s) => { window.__helper = s; }, helper); await ctx.addInitScript(bridge); }
  await ctx.route("**/api/directors", (r) => r.fulfill({ json: DIRECTORS }));
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  return { ctx, page };
}
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1);
const card = (page) => page.getByTestId("helper-card");

console.log("The helper card, in every state");
const sideways = [], small = [];
for (const [name, state] of Object.entries(STATES)) {
  for (const [w, h, tag] of [[1280, 900, "wide"], [400, 860, "phone"]]) {
    for (const scheme of ["light", "dark"]) {
      {
        const { ctx, page } = await open(w, h, scheme, state);
        await page.goto(`${base}/settings?s=directors`, { waitUntil: "load" });
        await card(page).waitFor();
        await page.waitForSelector(`[data-testid=helper-card][data-state=${state.running ? "running" : "stopped"}]`);
        await card(page).scrollIntoViewIfNeeded();
        if (!(await noOverflow(page))) sideways.push(`${name} ${tag} ${scheme}`);
        if (tag === "phone") {
          const low = await card(page).locator("button:not(.switch)").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height < 43.5).map((e) => `${e.textContent.trim()} ${Math.round(e.getBoundingClientRect().height)}px`));
          for (const l of low) small.push(`${name} ${scheme}: ${l}`);
        }
        await card(page).screenshot({ path: path.join(out, `helper-${name}-${tag}-${scheme}.png`) });
        await ctx.close();
      }
    }
  }
}
check("no state scrolls sideways at 400 px, light or dark", sideways.length === 0, sideways.join(" | "));
check("on a phone every button in the card is at least 44 px tall (the switch's own row is checked below)", small.length === 0, small.join(" | "));

console.log("What each state says and does");
{
  const { ctx, page } = await open(1280, 900, "light", STATES.running);
  await page.goto(`${base}/settings?s=directors`, { waitUntil: "load" });
  await card(page).waitFor();
  const text = await card(page).innerText();
  check("running: named, with its state", /Helper on this PC/.test(text) && (await page.getByTestId("helper-state").innerText()).includes("Running"));
  check("running: the server is listed, connected", /192\.168\.123\.47:8790/.test(text) && /Connected/.test(await page.getByTestId("helper-servers").innerText()));
  check("running: Claude ready with its version, Codex not installed", /Ready/.test(await page.getByTestId("helper-claude").innerText()) && /2\.1\.314/.test(await page.getByTestId("helper-claude").innerText()) && /Not installed/.test(await page.getByTestId("helper-codex").innerText()));
  const sw = page.getByTestId("helper-autostart");
  check("the switch is a real switch, named, and on", (await sw.getAttribute("role")) === "switch" && (await sw.getAttribute("aria-checked")) === "true" && /Keep Claude and Codex ready/.test((await sw.getAttribute("aria-labelledby")) ? await page.locator("#helper-keep").innerText() : ""));
  const box = await page.locator(".switch-row").boundingBox();
  check("its row is at least 44 px tall (a finger)", box.height >= 44, String(box.height));
  await sw.click();
  check("clicking it turns the start-with-the-computer setting off", (await page.evaluate(() => window.__calls.at(-1))).join() === "setAutostart,false" && (await sw.getAttribute("aria-checked")) === "false");
  await page.locator(".switch-row .col").first().click();                 // the whole row works, not only the knob
  check("so does clicking the words next to it", (await page.evaluate(() => window.__calls.at(-1))).join() === "setAutostart,true");
  await page.getByRole("button", { name: /Remove: 192\.168\.123\.47/ }).click();
  check("Remove sends the whole address", (await page.evaluate(() => window.__calls.at(-1))).join() === `removeServer,${SERVER}`);
  check("and the list says what happens next", /None yet/.test(await card(page).innerText()));
  await page.getByTestId("helper-refresh").click();
  check("Check again asks the helper to look again", (await page.evaluate(() => window.__calls.at(-1)))[0] === "refresh");
  await page.getByTestId("helper-stop").click();
  await page.waitForSelector("[data-testid=helper-card][data-state=stopped]");
  check("Stop stops it, and the card offers to start it with the consequence in words", /cannot use Claude or Codex/.test(await card(page).innerText()) && await page.getByTestId("helper-start").isVisible());
  await page.getByTestId("helper-start").click();
  await page.waitForSelector("[data-testid=helper-card][data-state=running]");
  check("Start brings it back", true);
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, "light", STATES.trouble);
  await page.goto(`${base}/settings?s=directors`, { waitUntil: "load" });
  await card(page).waitFor();
  const servers = await page.getByTestId("helper-servers").innerText();
  check("trouble: an unreachable server says so and why, a connecting one says it is connecting", /Can't reach it/.test(servers) && /The server is not answering\./.test(servers) && /Connecting/.test(servers), servers);
  const claude = await page.getByTestId("helper-claude").innerText();
  check("trouble: Claude asks to be signed in, with the reason", /Sign in/.test(claude) && /Open Claude Code once and log in/.test(claude), claude);
  check("trouble: Codex is ready", /Ready/.test(await page.getByTestId("helper-codex").innerText()));
  check("trouble: the switch is off", (await page.getByTestId("helper-autostart").getAttribute("aria-checked")) === "false");
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, "light", STATES.source);
  await page.goto(`${base}/settings?s=directors`, { waitUntil: "load" });
  await card(page).waitFor();
  const sw = page.getByTestId("helper-autostart");
  check("run from source: the switch is off limits and says why", (await sw.isDisabled()) && /installed app/.test(await card(page).innerText()));
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, "light", null, false);
  await page.goto(`${base}/settings?s=directors`, { waitUntil: "load" });
  await card(page).waitFor();
  check("in a plain browser the card says the app is needed", /Install and open the app/.test(await card(page).innerText()) && (await card(page).getAttribute("data-state")) === "no-app");
  await card(page).screenshot({ path: path.join(out, "helper-no-app-wide-light.png") });
  await ctx.close();
}
console.log("The Computers card on the Server page");
for (const [w, h, tag] of [[1280, 900, "wide"], [400, 860, "phone"]]) {
  for (const scheme of ["light", "dark"]) {
    {
      const { ctx, page } = await open(w, h, scheme, STATES.running);
      await page.goto(`${base}/server`, { waitUntil: "load" });
      const c = page.getByTestId("connected-computers");
      await c.waitFor();
      await page.getByTestId("computer-row").first().waitFor();
      if (tag === "wide" && scheme === "light") {
        const rows = await page.getByTestId("computer-row").all();
        const texts = await Promise.all(rows.map((r) => r.innerText()));
        check("two computers are listed, one connected and one remembered", rows.length === 2, texts.join(" | "));
        const here = texts.find((x) => /MSI-LAPTOP/.test(x)), gone = texts.find((x) => /Office Mac/.test(x));
        check("the connected one shows Claude ready and Codex needing sign-in", /Claude · Ready/.test(here) && /Codex · Needs sign-in/.test(here), here);
        check("the remembered one says it is not connected and when it was last seen", /Not connected/.test(gone) && /3 hours ago/.test(gone), gone);
      }
      if (!(await noOverflow(page))) check(`server page ${tag} ${scheme}: no sideways scrolling`, false);
      await c.screenshot({ path: path.join(out, `computers-${tag}-${scheme}.png`) });
      await ctx.close();
    }
  }
}
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route("**/api/directors", (r) => r.fulfill({ json: { ...DIRECTORS, directors: DIRECTORS.directors.slice(0, 2) } }));
  const page = await ctx.newPage();
  await page.goto(`${base}/server`, { waitUntil: "load" });
  await page.getByTestId("computers-empty").waitFor();
  check("with no computer yet, the card says what to do", /Open Ultimate Video Tool on a computer/.test(await page.getByTestId("computers-empty").innerText()));
  await ctx.close();
}

check("no page errors", errors.length === 0, errors.join(" | ").slice(0, 300));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
