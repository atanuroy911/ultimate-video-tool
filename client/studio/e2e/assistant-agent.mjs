// The Claude Code tab of the Assistant pane (docs/plans/PLAN-WORKBENCH.MD W12.4) in a real browser, with a scripted stand-in for window.vtDesktop.agents
// (the real bridge needs the desktop app; the runner behind it is tested by client/desktop/test-acp-agents.js).
//   VT_URL=http://localhost:5174 VT_PROJECT=<project id> node e2e/assistant-agent.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c2-mix";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const plain = await ctx.newPage();
await plain.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await plain.waitForSelector(".wb .wb-assistant-body", { timeout: 45000 });
await plain.getByRole("tab", { name: "Claude Code" }).click();
check("in a plain browser the tab says it needs the desktop app", await plain.getByText("Available in the desktop app").waitFor({ timeout: 5000 }).then(() => true, () => false));
// W13: in a plain browser Ctrl+L points the Director at the selected scene, and the reference goes with the message.
await plain.getByRole("tab", { name: "Director" }).click();
let posted = null;
await plain.route("**/director/chat**", async (route) => { posted = route.request().postDataJSON(); await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "test stops here" }) }); });
await plain.evaluate(() => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: "s2" })));
await plain.waitForTimeout(400);
await plain.mouse.click(5, 500);
await plain.keyboard.press("Control+l");
const dpill = plain.locator(".occ-chat .agent-pill, .agent-pills-draft .agent-pill").first();
check("Ctrl+L points the Director at the selected scene", await dpill.waitFor({ timeout: 5000 }).then(async () => /Scene \d/.test(await dpill.textContent()), () => false));
await plain.getByLabel("Message to the director").fill("Make [1] calmer");
await plain.keyboard.press("Enter");
await plain.waitForTimeout(800);
check("the Director gets the reference with the message", posted?.refs?.[0]?.scene === "s2" && posted.message === "Make [1] calmer", JSON.stringify(posted));
await plain.close();

const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
await page.addInitScript(() => {
  const listeners = new Set();
  const calls = [];
  const emit = (event) => setTimeout(() => listeners.forEach((cb) => cb({ conversationId: "c1", event })), 30);
  window.__calls = calls;
  window.vtDesktop = { agents: {
    status: async () => ({ found: true, logged_in: true, version: "2", reason: "", adapter: true }),
    list: async () => [{ sessionId: "old", title: "Make the title bigger", at: "2026-11-20" }],
    open: async (kind, projectId, o) => { calls.push(["open", kind, projectId, o && o.resume, o && o.model]); return { conversationId: "c1", resumed: !!(o && o.resume), note: "" }; },
    send: async (id, text, refs) => {
      calls.push(["send", text, refs]);
      emit({ type: "step", id: "t1", title: "Set caption style", tool: "mcp__video-tool__set_caption_style", status: "in_progress" });
      emit({ type: "text", text: "Making " });
      emit({ type: "text", text: "it bigger in [scene 3](vt://scene/s3), see [the end](vt://t/20) and [bad](https://evil.example)." });
      emit({ type: "step", id: "t1", title: "Set caption style", status: "completed" });
      if (/command/.test(text)) emit({ type: "permission", requestId: "r1", tool: "Bash", what: "run a command", title: "Run: dir", detail: JSON.stringify({ command: "dir C:\\Users" }) });
      else if (/limit/.test(text)) emit({ type: "error", kind: "login", message: "Claude Code is not signed in. Sign in, then try again." });
      else if (/break/.test(text)) emit({ type: "error", kind: "other", message: "Claude Code stopped unexpectedly." });
      else emit({ type: "done", stopReason: "end_turn" });
      return { ok: true };
    },
    stop: async () => { calls.push(["stop"]); emit({ type: "done", stopReason: "cancelled" }); },
    permission: async (id, rid, choice) => { calls.push(["permission", choice]); emit({ type: "text", text: choice === "deny" ? " Denied." : " Done." }); emit({ type: "done", stopReason: "end_turn" }); },
    signIn: async () => { calls.push(["signIn"]); },
    onEvent: (cb) => { listeners.add(cb); return () => listeners.delete(cb); },
  } };
});
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-assistant-body", { timeout: 45000 });
check("the Director is the default tab", await page.getByRole("tab", { name: "Director", selected: true }).isVisible());
await page.getByRole("tab", { name: "Claude Code" }).click();
const box = page.getByLabel("Message to Claude Code");
await box.waitFor({ timeout: 5000 });
check("the earlier conversation is offered", await page.getByRole("button", { name: /Continue “Make the title bigger”/ }).isVisible());
await page.locator(".agent-starters button").first().click();
check("an empty conversation offers starters, and one fills the message box", (await page.locator(".agent-starters button").count()) === 3 && (await box.inputValue()) === "Tighten the opening");
await box.fill("");

await page.getByLabel("Claude model").selectOption("sonnet");
await box.fill("Make the title bigger");
await page.keyboard.press("Enter");
await page.getByText("Making it bigger in").waitFor({ timeout: 5000 });
check("the reply streams in and the finished steps fold into one row", await page.locator(".agent-worked summary", { hasText: /Worked \d+s · 1 step/ }).isVisible()
  && await page.locator(".agent-worked .agent-steps li.completed", { hasText: "Set caption style" }).count() === 1);
check("a vt:// link is a button and an outside link is plain text", await page.locator(".agent-link", { hasText: "scene 3" }).isVisible() && await page.locator(".agent-turn a").count() === 0);
await page.locator(".agent-link", { hasText: "the end" }).click();
await page.waitForTimeout(400);
check("clicking a time link moves the playhead", /0:20|0:19|0:2\d/.test(await page.locator(".wb-viewer").textContent()), (await page.locator(".wb-viewer").textContent()).slice(-40));
check("the chosen model is passed to the agent", (await page.evaluate(() => window.__calls)).some((c) => c[0] === "open" && c[4] === "sonnet"));
check("a new conversation was opened for this video", (await page.evaluate(() => window.__calls)).some((c) => c[0] === "open" && c[2] === pid && !c[3]));

await box.fill("run a command please");
await page.keyboard.press("Enter");
const card = page.getByRole("alertdialog", { name: "Permission needed" });
await card.waitFor({ timeout: 5000 });
check("a command asks first, with what it would run", (await card.textContent()).includes("wants to run a command") && (await card.textContent()).includes("dir C:"));
check("Deny has the focus", await page.evaluate(() => document.activeElement?.textContent === "Deny"));
await page.getByRole("button", { name: "Deny" }).click();
await page.getByText("Denied.").waitFor({ timeout: 5000 });
check("Deny is passed to the agent", (await page.evaluate(() => window.__calls)).some((c) => c[0] === "permission" && c[1] === "deny"));
check("the card is gone after the answer", await card.count() === 0);

await box.fill("hit the limit");
await page.keyboard.press("Enter");
await page.getByRole("alert").waitFor({ timeout: 5000 });
check("a missing sign-in is said in plain words with a Sign in button", await page.getByRole("button", { name: "Sign in" }).isVisible());
await page.getByRole("button", { name: "Sign in" }).click();
check("Sign in asks the app to open the sign-in", (await page.evaluate(() => window.__calls)).some((c) => c[0] === "signIn"));

// W13.3: Ctrl+L with a scene selected points Claude Code at it.
await page.evaluate(() => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: "s2" })));
await page.waitForTimeout(400);
await page.mouse.click(5, 500);
await page.keyboard.press("Control+l");
const pill = page.locator(".agent-pills-draft .agent-pill").first();
check("Ctrl+L with a scene selected makes a pill", await pill.waitFor({ timeout: 5000 }).then(async () => /Scene \d/.test(await pill.textContent()), () => false), await pill.textContent().catch(() => ""));
check("and the message box has the keyboard", await page.evaluate(() => document.activeElement?.getAttribute("aria-label") === "Message to Claude Code"));
await page.keyboard.type("Make [1] calmer");
await page.keyboard.press("Enter");
await page.waitForTimeout(600);
const sent = (await page.evaluate(() => window.__calls)).filter((c) => c[0] === "send").pop();
check("the reference goes to the agent with the scene and its times", sent && sent[2]?.[0]?.kind === "scene" && sent[2][0].scene === "s2" && sent[2][0].to > sent[2][0].from, JSON.stringify(sent && sent[2]));
check("the pill is cleared after sending", await page.locator(".agent-pills-draft").count() === 0);
await box.fill("please break");
await page.keyboard.press("Enter");
await page.getByRole("button", { name: "Try again" }).waitFor({ timeout: 5000 });
const sendsBefore = (await page.evaluate(() => window.__calls)).filter((c) => c[0] === "send" && c[1] === "please break").length;
await page.getByRole("button", { name: "Try again" }).click();
await page.waitForTimeout(500);
check("a failed reply offers Try again, which sends the same message", (await page.evaluate(() => window.__calls)).filter((c) => c[0] === "send" && c[1] === "please break").length === sendsBefore + 1);
// W13.3: a scene's menu points the assistant at it, like Ctrl+L
await page.getByRole("button", { name: "Scene 3 actions" }).click();
await page.getByRole("button", { name: /Ask the assistant about this/ }).click();
await page.waitForTimeout(600);
check("a scene's menu points Claude Code at that scene", /Scene 3/.test(await page.locator(".agent-pills-draft .agent-pill").first().textContent().catch(() => "")));
await page.locator(".agent-pills-draft button").first().click();
await page.getByRole("button", { name: "New conversation" }).click();
check("New conversation clears the chat and the next message opens a fresh one", (await page.locator(".agent-turn").count()) === 0 && (await page.locator(".agent-starters button").count()) === 3);
await page.getByRole("tab", { name: "Director" }).click();
check("the Director conversation is still there", await page.getByPlaceholder(/Tell the director/i).isVisible().catch(() => false));
await page.screenshot({ path: process.env.VT_SHOT_PNG || "assistant-agent.png" });
check("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
