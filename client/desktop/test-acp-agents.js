/* The agent runner against a fake ACP agent (docs/plans/PLAN-WORKBENCH.MD W12.2, W12.3 and W12.5), plain Node: node test-acp-agents.js */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const V = require("./acp-validate");
const { createAgents, humanTitle } = require("./acp-agents");
const { instructions, toPrompt } = require("./acp-instructions");

const wait = (cond, what, ms = 8000) => new Promise((resolve, reject) => {
  const t0 = Date.now();
  const tick = () => { const v = cond(); if (v) return resolve(v); if (Date.now() - t0 > ms) return reject(new Error("timed out waiting for " + what)); setTimeout(tick, 20); };
  tick();
});

// ---- the checks on what the window sends ----
assert.equal(V.kind("claude"), "claude");
assert.throws(() => V.kind("rm"), /Claude Code or Codex/);
for (const bad of ["../x", "a b", "", "x".repeat(65), 5, null]) assert.throws(() => V.id(bad), /not valid/);
assert.equal(V.id("2026-11-20_watch"), "2026-11-20_watch");
assert.throws(() => V.text("  "), /Write a message/);
assert.throws(() => V.text("x".repeat(100 * 1024 + 1)), /too long/);
const png = Buffer.alloc(100, 1).toString("base64");
assert.deepEqual(V.images([{ mime: "image/png", data: png }]), [{ mime: "image/png", data: png }]);
assert.throws(() => V.images([{ mime: "image/gif", data: png }]), /PNG, JPEG or WebP/);
assert.throws(() => V.images(Array(7).fill({ mime: "image/png", data: png })), /At most 6/);
assert.throws(() => V.images([{ mime: "image/png", data: "A".repeat(7 * 1024 * 1024) }]), /5 MB/);
assert.throws(() => V.images([{ mime: "image/png", data: "not base64!" }]), /not valid/);
assert.deepEqual(V.refs([{ kind: "scene", scene: "s3", evil: "x" }]), [{ kind: "scene", scene: "s3" }], "unknown fields are dropped");
assert.throws(() => V.refs([{ kind: "file", path: "C:\\secret" }]), /not valid/);
assert.throws(() => V.refs(Array(51).fill({ kind: "scene", scene: "s1" })), /At most 50/);
assert.throws(() => V.refs([{ kind: "time", t: "NaN" }]), /not valid/);
assert.throws(() => V.choice("always"), /Choose/);

// ---- what the agent is told ----
assert.match(instructions({ title: "My `video`\nline", projectId: "p1" }), /My video line/);
assert.match(instructions({ title: "x", projectId: "p1" }), /vt:\/\/scene\/s3/);
assert.equal(toPrompt("Make it bigger", []), "Make it bigger");
assert.equal(toPrompt("Fix [1]", [{ kind: "scene", scene: "s3", from: 4, to: 6.1, label: "the hook" }]), 'Fix [1]\n\n<video_references>\n[1] scene s3 · 0:04.0–0:06.1 · vt://scene/s3 · "the hook"\n</video_references>');
assert.match(toPrompt("x", [{ kind: "element", scene: "s3", index: 2, label: "Small habits" }]), /\[1\] element s3#2 · vt:\/\/element\/s3\/2 · "Small habits"/);
assert.equal(humanTitle("mcp__video-tool__set_caption_style"), "Set caption style");
assert.equal(humanTitle(""), "Working");
assert.equal(humanTitle("ToolSearch"), "Looking for the right tool");
assert.equal(humanTitle("SomeNewTool"), "Some new tool");

(async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-acp-"));
  const record = path.join(home, "record.jsonl");
  const events = [];
  const agents = createAgents({ home, version: "9.9.9", emit: (id, e) => events.push({ id, ...e }), getServer: () => "http://127.0.0.1:8790", getKey: () => "secret-key",
    fake: path.join(__dirname, "test", "fake-acp-agent.mjs"), bridge: path.join(__dirname, "mcp-bridge.js"), env: { FAKE_RECORD: record }, cancelGrace: 400, permissionTimeout: 600 });
  const records = () => (fs.existsSync(record) ? fs.readFileSync(record, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l)) : []);
  try {
    // open: our MCP server goes to the agent with the server's address and key, and the agent gets a scratch folder, never the server's files
    const opened = await agents.open("claude", "watch-1", { title: "Watch" });
    assert.ok(/^[\w-]{1,64}$/.test(opened.conversationId));
    assert.equal(opened.resumed, false);
    assert.deepEqual(opened.models, { current: "sonnet", available: [{ id: "sonnet", name: "Sonnet" }, { id: "opus", name: "Opus" }] });
    const made = records().find((r) => r.method === "new");
    assert.equal(made.mcpServers.length, 1);
    assert.equal(made.mcpServers[0].name, "video-tool");
    assert.ok(made.mcpServers[0].args[0].endsWith("mcp-bridge.js"));
    const env = Object.fromEntries(made.mcpServers[0].env.map((e) => [e.name, e.value]));
    assert.equal(env.VT_SERVER, "http://127.0.0.1:8790/mcp");
    assert.equal(env.VT_TOKEN, "secret-key");
    assert.equal(path.resolve(made.cwd), path.resolve(home, "agents", "watch-1"));
    assert.equal(made.meta.claudeCode.options.allowDangerouslySkipPermissions, false, "no full-access mode");
    assert.ok(made.meta.claudeCode.options.allowedTools.includes("mcp__video-tool__*"));
    assert.match(made.meta.systemPrompt.append, /video-tool/);
    const id = opened.conversationId;

    // a normal turn: streamed text, our tool allowed at once (no card), Bash asks, Deny is respected
    agents.send(id, "Make the title bigger [1]", [{ kind: "scene", scene: "s1" }], [{ mime: "image/png", data: png }]);
    const card = await wait(() => events.find((e) => e.type === "permission"), "the permission card");
    assert.equal(card.tool, "Bash");
    assert.equal(card.what, "run a command");
    assert.match(card.detail, /dir C:/);
    assert.equal(events.filter((e) => e.type === "permission").length, 1, "our own tool asked nothing");
    agents.permission(id, card.requestId, "deny");
    await wait(() => events.find((e) => e.type === "done"), "the end of the turn");
    const text = events.filter((e) => e.type === "text").map((e) => e.text).join("");
    assert.equal(text, "Hello there Denied.");
    const steps = events.filter((e) => e.type === "step");
    assert.equal(steps[0].title, "Set caption style");
    assert.equal(steps[0].tool, "mcp__video-tool__set_caption_style");
    assert.ok(steps.some((s) => s.id === "t1" && s.status === "completed"));
    const sent = records().find((r) => r.method === "prompt");
    assert.match(sent.text, /Make the title bigger \[1\][\s\S]*<video_references>[\s\S]*\[1\] scene s1/);
    assert.equal(sent.images, 1);
    assert.equal(records().find((r) => r.method === "own-tool-permission").outcome.outcome, "selected");
    assert.equal(records().find((r) => r.method === "bash-permission").outcome.optionId, "reject");

    // "Allow for this chat" is remembered: the second turn does not ask again
    events.length = 0;
    agents.send(id, "again", [], []);
    const second = await wait(() => events.find((e) => e.type === "permission"), "the second card");
    agents.permission(id, second.requestId, "chat");
    await wait(() => events.find((e) => e.type === "done"), "turn 2");
    events.length = 0;
    agents.send(id, "a third time", [], []);
    await wait(() => events.find((e) => e.type === "done"), "turn 3");
    assert.equal(events.filter((e) => e.type === "permission").length, 0, "allowed for this chat");
    assert.match(events.filter((e) => e.type === "text").map((e) => e.text).join(""), /Done\./);

    // a question nobody answers is denied after the time limit
    const lonely = await agents.open("claude", "watch-2");
    events.length = 0;
    agents.send(lonely.conversationId, "hello", [], []);
    await wait(() => events.find((e) => e.type === "done" && e.id === lonely.conversationId), "the time limit");
    assert.match(events.filter((e) => e.id === lonely.conversationId && e.type === "text").map((e) => e.text).join(""), /Denied\./);

    // stop: a turn that never ends is cancelled
    events.length = 0;
    agents.send(id, "slow please", [], []);
    await wait(() => events.find((e) => e.type === "text" && e.text === "Working"), "the slow turn to begin");
    assert.throws(() => agents.send(id, "too soon", [], []), /still working/);
    const stopped = await agents.stop(id);
    assert.equal(stopped.killed, false, "the agent honoured the cancel");
    await wait(() => events.find((e) => e.type === "done" && e.stopReason === "cancelled"), "cancelled");

    // errors in plain words, with no raw text from the agent
    events.length = 0;
    agents.send(id, "limit now", [], []);
    const err = await wait(() => events.find((e) => e.type === "error"), "the error");
    assert.equal(err.kind, "limit");
    assert.equal(err.message, "Claude Code's usage limit is reached. Try again when it resets.");

    // the list of conversations per video, and resuming one
    const list = agents.list("watch-1");
    assert.equal(list.length, 1);
    assert.equal(list[0].agent, "claude");
    assert.equal(list[0].title, "Make the title bigger [1]".slice(0, 60) === list[0].title ? list[0].title : "Watch");
    const again = await agents.open("claude", "watch-1", { resume: list[0].sessionId });
    assert.equal(again.resumed, true);
    assert.ok(records().some((r) => r.method === "resume" && r.sessionId === list[0].sessionId && r.mcpServers[0].name === "video-tool"));

    // the other checks reach the runner too
    await assert.rejects(() => agents.open("claude", "../etc"), /not valid/);
    assert.throws(() => agents.send("nope", "x"), /not open/);
    assert.throws(() => agents.permission(id, "zz", "allow"), /Choose/);
    assert.equal(agents.status("codex").found, false);
    assert.throws(() => agents.status("bash"), /Claude Code or Codex/);

    // closing everything ends the agent processes
    const procs = [...agents._sessions.values()].map((s) => s.proc);
    agents.closeAll();
    await wait(() => procs.every((p) => p.exitCode !== null || p.signalCode), "the agents to end");
    console.log("ACP agents: validators, open, streaming, permissions, stop, errors, list and resume all pass against the fake agent.");
  } finally {
    agents.closeAll();
    await new Promise((r) => setTimeout(r, 300));
    try { fs.rmSync(home, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 }); } catch { /* a stopping agent may still hold its folder; the temp folder is cleared by the system */ }
  }
})().catch((e) => { console.error(e); process.exit(1); });

// W13.2: the same references read the same in the Director chat (server/vt/assistant_refs.py); shared cases in tests/fixtures/refs.json.
for (const c of JSON.parse(require("fs").readFileSync(require("path").join(__dirname, "..", "..", "tests", "fixtures", "refs.json"), "utf8"))) {
  require("assert").equal(require("./acp-instructions").toPrompt(c.text, c.refs), c.expected);
}
console.log("References read the same as the Director's (shared fixture).");
