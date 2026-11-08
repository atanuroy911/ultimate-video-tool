// The graphics cards on the Server page and in the setup wizard (PLAN-PERFECT K3, K4): a switch per card, the question when nobody has answered, which card does what,
// the engines Video Tool works with in plain words, the dot on the Server item, phone and wide, light and dark.
// The server's answers are stood in for by the script below, so this needs no GPU server (the rest of the pages read whatever the dev server proxies to):
//   cd client/studio && VT_SERVER_URL=http://192.168.123.47:8790 npx vite --port 5176 --strictPort --host 127.0.0.1
//   VT_URL=http://127.0.0.1:5176 node e2e/gpu_card.mjs [out dir]
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:5176";
const out = process.argv[2] || "e2e/out/gpu";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

const clone = (x) => JSON.parse(JSON.stringify(x));
const V100 = { index: 0, name: "Tesla V100-PCIE-16GB", uuid: "GPU-v100", free_gb: 6.2, total_gb: 16, load: 90, allowed: false, using: [{ label: "python3", gb: 9.7, ours: false }, { label: "Ollama", gb: 1.17, ours: false }] };
const RTX = { index: 1, name: "NVIDIA GeForce RTX 3060", uuid: "GPU-3060", free_gb: 11.4, total_gb: 12, load: 3, allowed: true, using: [] };
const job = (c, why) => ({ gpu: c.uuid, name: c.name, index: c.index, why });
const SAVED = { primary: "auto", render: "primary", speech: "primary", ai: "primary", pictures: "primary" };
const jobs = (c) => ({ render: job(c, "automatic"), speech: job(c, "automatic"), ai: job(c, "automatic"), pictures: job(c, "automatic") });
const BLOCKED_TEXT = "was already running on this computer before Video Tool. It is using Tesla V100-PCIE-16GB (1.17 GB), a card Video Tool is not allowed to use. Video Tool did not start it and does not change it, so it keeps asking it for work. To keep Video Tool's work off that card, use Video Tool's own copy.";
const ENGINES = [
  { id: "ollama", label: "Ollama", source: "existing", url: "http://127.0.0.1:11434", code: "existing_blocked", offer_own: true, own_installed: true, on: [{ index: 0, name: "Tesla V100-PCIE-16GB", gb: 1.17, allowed: false, ours: false }], message: "Ollama " + BLOCKED_TEXT },
  { id: "comfy", label: "ComfyUI", source: "existing", url: "http://127.0.0.1:8188", code: "existing_blocked", offer_own: true, own_installed: false, on: [{ index: 0, name: "Tesla V100-PCIE-16GB", gb: 6, allowed: false, ours: false }], message: "ComfyUI " + BLOCKED_TEXT.replace("1.17 GB", "6 GB") },
];
const ANSWERED = { cards: [V100, RTX], saved: SAVED, allowed_saved: ["GPU-3060"], needs_choice: false, restart_needed: false, jobs: jobs(RTX), separate_programs: {}, engines: ENGINES, pinned_by_launcher: null };
const UNANSWERED = { ...clone(ANSWERED), allowed_saved: null, needs_choice: true };
const BOTH = { ...clone(ANSWERED), cards: [{ ...V100, allowed: true }, RTX], allowed_saved: ["GPU-v100", "GPU-3060"], engines: [] };
const NONE = { ...clone(ANSWERED), cards: [{ ...V100, allowed: false }, { ...RTX, allowed: false }], allowed_saved: [], jobs: { render: job({ uuid: null, name: null, index: null }, "no card"), speech: job({}, ""), ai: job({}, ""), pictures: job({}, "") }, engines: [] };
const RESTART = { ...clone(ANSWERED), restart_needed: true };
const OWN_RUNNING = { ...clone(ANSWERED), engines: [{ ...ENGINES[0], source: "own", code: "own_running", offer_own: false, on: [{ index: 1, name: "NVIDIA GeForce RTX 3060", gb: 3, allowed: true, ours: true }], message: "Video Tool's own Ollama is running on NVIDIA GeForce RTX 3060 (3 GB)." }, ENGINES[1]] };
const SETUP = {
  step: "welcome", done: false, choices: {}, bundles: ["pictures"], models_dir: "", install_dir: "", steps: [], server: { name: "GPU-SERVER", data_dir: "/data", os: "Linux" }, existing: {}, gpu: null, recommended_gpu: 1,
  hardware: { summary: "", disk_free_gb: 116, ram_gb: 47, data_dir: "/data", gpus: [{ index: 0, name: V100.name, memory_gb: 16 }, { index: 1, name: RTX.name, memory_gb: 12 }] },
  recommended: { ollama: "local", comfy: "local" }, engines: [{ id: "ollama", label: "Ollama", about: "Language AI", installable: true, mode: "off" }, { id: "comfy", label: "ComfyUI", about: "Pictures and clips", installable: true, mode: "off" }],
};

// what the server does with a save, as far as this page can tell
function applySave(data, body) {
  const next = clone(data);
  if (body.allowed) {
    next.cards.forEach((c) => { c.allowed = body.allowed.includes(c.uuid); });
    next.allowed_saved = body.allowed; next.needs_choice = false;
  }
  for (const k of ["primary", "render", "speech", "ai", "pictures"]) if (body[k]) next.saved[k] = body[k];
  return next;
}

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const errors = [];
async function open(width, height, scheme, data, setup = null) {
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
  await ctx.addInitScript((th) => { try { localStorage.setItem("vt-theme", th); } catch {} }, scheme);
  const seen = { posts: [], puts: [], setupPuts: [], data };
  await ctx.route("**/api/system/stats", async (r) => {                                  // the real numbers, with the one new field this page reads
    try { const res = await r.fetch(); const j = await res.json(); j.needs_gpu_choice = !!seen.data.needs_choice; await r.fulfill({ response: res, json: j }); } catch { await r.continue(); }
  });
  await ctx.route("**/api/system/gpus", (r) => r.fulfill({ json: seen.data }));
  await ctx.route("**/api/system/gpu", (r) => { const body = JSON.parse(r.request().postData() || "{}"); seen.puts.push(body); seen.data = applySave(seen.data, body); r.fulfill({ json: { ...seen.data, restarting: body.allowed ? ["ollama"] : [] } }); });
  await ctx.route("**/api/system/engine-own", (r) => { seen.posts.push(JSON.parse(r.request().postData() || "{}")); seen.data = clone(OWN_RUNNING); r.fulfill({ json: { engine: "ollama", source: "own", starting: true } }); });
  if (setup) {
    await ctx.route("**/api/setup", (r) => { if (r.request().method() === "PUT") { seen.setupPuts.push(JSON.parse(r.request().postData() || "{}")); return r.fulfill({ json: setup }); } return r.fulfill({ json: setup }); });
  }
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  return { ctx, page, seen };
}
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1);
const card = (page) => page.getByTestId("gpu-assignment");
const goto = async (page) => { await page.goto(`${base}/server`, { waitUntil: "load" }); await card(page).waitFor(); await page.getByTestId("gpu-cards").waitFor(); await card(page).scrollIntoViewIfNeeded(); };

console.log("Every state, wide and phone, light and dark");
const sideways = [], small = [];
const STATES = process.env.SKIP_STATES ? {} : { answered: ANSWERED, unanswered: UNANSWERED, both: BOTH, none: NONE, restart: RESTART };       // SKIP_STATES=1 reruns only the behaviour checks
for (const [name, data] of Object.entries(STATES)) {
  for (const [w, h, tag] of [[1280, 900, "wide"], [400, 860, "phone"]]) {
    for (const scheme of ["light", "dark"]) {
      {
        const { ctx, page } = await open(w, h, scheme, data);
        await goto(page);
        if (!(await noOverflow(page))) sideways.push(`${name} ${tag} ${scheme}`);
        if (tag === "phone") {
          const low = await card(page).locator("button:not(.switch)").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height < 43.5).map((e) => `${e.textContent.trim()} ${Math.round(e.getBoundingClientRect().height)}px`));
          for (const l of low) small.push(`${name} ${scheme}: ${l}`);
          const rows = await card(page).locator("li").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height < 43.5).length);
          if (rows) small.push(`${name} ${scheme}: ${rows} list rows shorter than 44 px`);
        }
        await card(page).screenshot({ path: path.join(out, `gpu-${name}-${tag}-${scheme}.png`) });
        await ctx.close();
      }
    }
  }
}
check("no state scrolls sideways at 400 px, light or dark", sideways.length === 0, sideways.join(" | "));
check("on a phone every button is at least 44 px tall and every list row at least 44 px", small.length === 0, small.join(" | "));

console.log("The cards and their switches");
{
  const { ctx, page, seen } = await open(1280, 900, "light", ANSWERED);
  await goto(page);
  const v = page.getByTestId("gpu-switch-0"), r = page.getByTestId("gpu-switch-1");
  check("each card is a row with a real, named switch", (await v.getAttribute("role")) === "switch" && /Video Tool may use this card: Tesla V100/.test((await v.getAttribute("aria-label")) || ""));
  check("the V100 is off and the 3060 is on", (await v.getAttribute("aria-checked")) === "false" && (await r.getAttribute("aria-checked")) === "true");
  check("each row says what is using the card, in words", /python3 is using 9\.7 GB\. Ollama is using 1\.17 GB\./.test(await page.getByTestId("gpu-using-0").innerText()) && /Nothing else is using it\./.test(await page.getByTestId("gpu-using-1").innerText()));
  check("and how much of it is free", /6\.2 of 16 GB free/.test(await page.getByTestId("gpu-card-0").innerText()));
  check("with one card on there is nothing to choose between, so no job rows are shown", (await page.getByTestId("gpu-jobs").count()) === 0);
  await v.click();
  await page.waitForFunction(() => document.querySelector("[data-testid=gpu-switch-0]")?.getAttribute("aria-checked") === "true");
  check("turning the V100 on saves exactly the two cards", seen.puts.length === 1 && JSON.stringify(seen.puts[0].allowed.sort()) === JSON.stringify(["GPU-3060", "GPU-v100"]), JSON.stringify(seen.puts));
  check("two cards on: the jobs appear, each with only the cards that are on", (await page.getByTestId("gpu-jobs").count()) === 1 && (await page.locator("#gpu-render option").count()) === 3);
  check("the status line tells a screen reader what changed", /Video Tool may now use: Tesla V100-PCIE-16GB, NVIDIA GeForce RTX 3060\./.test(await card(page).locator("[role=status]").innerText()));
  check("changing a job saves only that job", await (async () => { await page.locator("#gpu-render").selectOption("GPU-v100"); await page.waitForTimeout(150); return JSON.stringify(seen.puts.at(-1)) === JSON.stringify({ render: "GPU-v100" }); })());
  await r.click();
  await page.waitForFunction(() => document.querySelector("[data-testid=gpu-switch-1]")?.getAttribute("aria-checked") === "false");
  check("turning the 3060 off leaves only the V100 allowed, and its status line says the engine restarts", JSON.stringify(seen.puts.at(-1).allowed) === JSON.stringify(["GPU-v100"]) && /restarts on its new card/.test(await card(page).locator("[role=status]").innerText()));
  await v.click();
  await page.waitForFunction(() => document.querySelector("[data-testid=gpu-switch-0]")?.getAttribute("aria-checked") === "false");
  check("turning the last card off is allowed and says what it means", (await page.getByTestId("gpu-none-on").count()) === 1 && /much slower/.test(await page.getByTestId("gpu-none-on").innerText()));
  await ctx.close();
}

console.log("Three cards, two of them on");
{
  const BIG = { index: 2, name: "NVIDIA GeForce RTX 3090", uuid: "GPU-3090", free_gb: 20, total_gb: 24, load: 0, allowed: true, using: [] };
  const THREE = { ...clone(ANSWERED), cards: [V100, RTX, BIG], allowed_saved: ["GPU-3060", "GPU-3090"], engines: [] };
  const { ctx, page } = await open(1280, 900, "light", THREE);
  await goto(page);
  const texts = await page.locator("#gpu-render option").allInnerTexts();
  check("the job choices list only the cards that are switched on", texts.length === 3 && !texts.some((x) => /V100/.test(x)) && texts.some((x) => /3090/.test(x)), texts.join(" | "));
  await ctx.close();
}

console.log("A server older than the app");
{
  const OLD = { cards: [{ index: 0, name: V100.name, uuid: V100.uuid, free_gb: 6.2, total_gb: 16, load: 90, allowed: true }, { index: 1, name: RTX.name, uuid: RTX.uuid, free_gb: 11.4, total_gb: 12, load: 3, allowed: true }],
    saved: { primary: "auto", render: "primary", speech: "primary" }, jobs: { render: job(RTX, "x"), speech: job(RTX, "x") }, separate_programs: {}, pinned_by_launcher: null };
  const { ctx, page } = await open(1280, 900, "light", OLD);
  await page.goto(`${base}/server`, { waitUntil: "load" });
  await card(page).waitFor();
  check("a server that answers the old way does not break the page: the card says the server must be updated", /can't choose graphics cards\. Update it/.test(await card(page).innerText()) && /older than this app/.test(await card(page).innerText()));
  check("and the rest of the Server page is still there", (await page.getByTestId("connected-computers").count()) === 1 && errors.length === 0, errors.join(" | ").slice(0, 200));
  await ctx.close();
}

console.log("When nobody has answered yet");
{
  const { ctx, page, seen } = await open(1280, 900, "light", UNANSWERED);
  await goto(page);
  const note = page.getByTestId("gpu-needs-choice");
  check("it says nobody has chosen and which one card is used meanwhile", /Choose which cards Video Tool may use\. Until then it uses only NVIDIA GeForce RTX 3060\./.test(await note.innerText()), await note.innerText());
  const dot = page.locator("[data-testid=gpu-choice-dot]:visible");
  await dot.first().waitFor({ timeout: 8000 });
  check("the Server item in the sidebar has a small dot, named for a screen reader, and there is no banner", (await dot.count()) === 1 && /choice is waiting/.test((await dot.first().getAttribute("aria-label")) || "") && (await page.locator(".banner").count()) === 0);
  await page.getByTestId("gpu-keep").click();
  await page.waitForFunction(() => !document.querySelector("[data-testid=gpu-needs-choice]"));
  check("'Keep this' saves the cards that are on as the answer", JSON.stringify(seen.puts.at(-1)) === JSON.stringify({ allowed: ["GPU-3060"] }), JSON.stringify(seen.puts));
  await page.waitForFunction(() => !document.querySelector("[data-testid=gpu-choice-dot]"), null, { timeout: 8000 });
  check("and the dot goes away", (await page.locator("[data-testid=gpu-choice-dot]").count()) === 0);
  await ctx.close();
}
{
  const { ctx, page } = await open(400, 860, "dark", UNANSWERED);
  await page.goto(`${base}/server`, { waitUntil: "load" });
  await page.locator("[data-testid=gpu-choice-dot]:visible").first().waitFor({ timeout: 8000 });
  check("on a phone the dot sits on the Server tab of the bottom bar", (await page.locator(".tabbar [data-testid=gpu-choice-dot]").count()) === 1);
  await page.screenshot({ path: path.join(out, "gpu-tabbar-phone-dark.png") });
  await ctx.close();
}
{
  const { ctx, page } = await open(1280, 900, "light", RESTART);
  await goto(page);
  check("after a change, it says programs already started keep their old cards until the server restarts", /keep their old card until the server restarts/.test(await page.getByTestId("gpu-restart").innerText()));
  await ctx.close();
}

console.log("The engines Video Tool works with");
{
  const { ctx, page, seen } = await open(1280, 900, "light", ANSWERED);
  await goto(page);
  const ollama = page.getByTestId("engine-ollama"), comfy = page.getByTestId("engine-comfy");
  const text = await ollama.innerText();
  check("Ollama, on a card Video Tool may not use, says so in words", /already running on this computer before Video Tool/.test(text) && /Tesla V100-PCIE-16GB \(1\.17 GB\)/.test(text) && /not allowed to use/.test(text), text);
  check("and says what Video Tool does and does not do about it", /did not start it and does not change it/.test(text) && /use Video Tool's own copy/.test(text));
  check("it offers Video Tool's own copy as a button", await page.getByTestId("engine-ollama-own").isVisible());
  const ctext = await comfy.innerText();
  check("ComfyUI says its own copy is not installed yet and where to install it, with no button", /isn't installed yet/.test(ctext) && /Set up… under AI programs/.test(ctext) && (await page.getByTestId("engine-comfy-own").count()) === 0, ctext);
  check("the two engines use the names the rest of the app uses", /Language AI \(Ollama\)/.test(text) && /Pictures & clips \(ComfyUI\)/.test(ctext));
  await page.getByTestId("engine-ollama-own").click();
  await ollama.locator("text=own Ollama is running").waitFor();
  check("choosing it asks the server for exactly that engine", seen.posts.length === 1 && seen.posts[0].engine === "ollama", JSON.stringify(seen.posts));
  check("and the row then says Video Tool's own copy is running, with no button", /Video Tool's own Ollama is running on NVIDIA GeForce RTX 3060/.test(await ollama.innerText()) && (await page.getByTestId("engine-ollama-own").count()) === 0);
  await page.getByTestId("gpu-assignment").screenshot({ path: path.join(out, "gpu-engines-own-wide-light.png") });
  await ctx.close();
}

console.log("The setup question in the wizard");
{
  const { ctx, page, seen } = await open(1280, 900, "light", UNANSWERED, SETUP);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.locator(".banner").getByRole("button", { name: "Set up", exact: true }).click();
  const sheet = page.getByRole("dialog");
  await sheet.waitFor();
  check("with two cards the wizard has five steps", /Step 1 of 5|1 of 5|1 \/ 5/.test(await sheet.locator(".ios-nav-title").innerText()), await sheet.locator(".ios-nav-title").innerText());
  await sheet.getByRole("button", { name: /^Continue$/ }).click();
  const step = sheet.getByTestId("gpu-assignment");
  await step.waitFor();
  check("the second step is the question, with its own title and no card frame of its own", /Which graphics cards may Video Tool use\?/.test(await sheet.locator(".ios-title").innerText()) && (await step.getAttribute("data-mode")) === "setup" && !/card-pad/.test((await step.getAttribute("class")) || ""));
  check("it lists both cards with their switches", (await sheet.getByTestId("gpu-switch-0").count()) === 1 && (await sheet.getByTestId("gpu-switch-1").count()) === 1);
  check("the old 'Graphics card for a new install' choice is gone from the folders step", await (async () => { await sheet.getByTestId("gpu-not-now").click(); await sheet.locator("text=Where to keep downloads").first().waitFor(); return (await sheet.locator("text=Graphics card for a new install").count()) === 0; })());
  for (let k = 0; k < 40 && !seen.setupPuts.some((b) => b.step === "storage"); k++) await page.waitForTimeout(50);       // the wizard saves where it is, then the step, one after the other
  check("'Not now' moved on without saving an answer", !seen.puts.length && seen.setupPuts.some((b) => b.step === "storage"), JSON.stringify(seen.setupPuts.slice(-2)));
  await sheet.getByRole("button", { name: /^Back$/ }).click();
  await step.waitFor();
  await sheet.getByTestId("gpu-switch-0").click();
  await page.waitForFunction(() => document.querySelector("[data-testid=gpu-switch-0]")?.getAttribute("aria-checked") === "true");
  await sheet.getByTestId("gpu-use-these").click();
  await sheet.locator("text=Where to keep downloads").first().waitFor();
  check("'Use these cards' saves the answer and moves on", seen.puts.length === 2 && JSON.stringify(seen.puts.at(-1).allowed.sort()) === JSON.stringify(["GPU-3060", "GPU-v100"]), JSON.stringify(seen.puts));
  await sheet.getByRole("button", { name: /^Back$/ }).click();
  await sheet.getByTestId("gpu-switch-1").waitFor();
  await page.waitForTimeout(700);                                                         // the sheet fades in
  await page.screenshot({ path: path.join(out, "gpu-setup-step-wide-light.png") });
  await ctx.close();
}
for (const [w, h, scheme] of [[400, 860, "dark"], [1280, 900, "dark"], [400, 860, "light"]]) {
  const { ctx, page } = await open(w, h, scheme, UNANSWERED, SETUP);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.locator(".banner").getByRole("button", { name: "Set up", exact: true }).click();
  const sheet = page.getByRole("dialog");
  await sheet.waitFor();
  await sheet.getByRole("button", { name: /^Continue$/ }).click();
  await sheet.getByTestId("gpu-assignment").waitFor();
  if (!(await noOverflow(page))) check(`the setup step does not scroll sideways (${w} ${scheme})`, false);
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(out, `gpu-setup-step-${w < 500 ? "phone" : "wide"}-${scheme}.png`) });
  await ctx.close();
}
{
  const one = clone(SETUP); one.hardware.gpus = [one.hardware.gpus[1]];
  const { ctx, page } = await open(1280, 900, "light", { ...clone(ANSWERED), cards: [RTX] }, one);
  await page.goto(`${base}/`, { waitUntil: "load" });
  await page.locator(".banner").getByRole("button", { name: "Set up", exact: true }).click();
  const sheet = page.getByRole("dialog");
  await sheet.waitFor();
  check("with one card there is nothing to ask: four steps, no question", /of 4/.test(await sheet.locator(".ios-nav-title").innerText()) && (await sheet.getByTestId("gpu-assignment").count()) === 0);
  await ctx.close();
}
check("no page errors", errors.length === 0, errors.join(" | ").slice(0, 400));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
