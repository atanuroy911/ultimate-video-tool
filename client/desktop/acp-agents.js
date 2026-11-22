/* Claude Code (and Codex, when set up) inside the app, over the Agent Client Protocol (docs/plans/PLAN-WORKBENCH.MD W12, PLAN-CODE-NATIVE-EDITOR C6).
 *
 * The real program runs as the person's own signed-in Claude Code, started by a small adapter (@agentclientprotocol/claude-agent-acp) that speaks ACP on its
 * stdin and stdout. This module starts it, relays the conversation to the app window as plain events, and answers the agent's permission questions:
 * our own `video-tool` MCP tools are allowed at once, everything else asks the person (Allow once / Allow for this chat / Deny). No full-access mode is ever
 * set, and the agent is offered no file system and no terminal of ours. The window gets events and never a path, an environment variable or a key. */
const { spawn } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { Readable, Writable } = require("stream");
const V = require("./acp-validate");
const { instructions, toPrompt } = require("./acp-instructions");
const director = require("./director-runner");

const OWN_SERVER = "video-tool";
const PERMISSION_TIMEOUT_MS = 10 * 60 * 1000;
const CANCEL_GRACE_MS = 5000;
const STDERR_LINES = 200;

let sdk = null;
const loadSdk = async () => sdk || (sdk = await import("@agentclientprotocol/sdk"));
const unpacked = (p) => p.replace(/app\.asar([\\/])/, "app.asar.unpacked$1");

/** The adapter's entry file for an agent, or null when it is not set up on this computer. */
function adapterEntry(kind, home) {
  if (kind === "claude") {
    try { return unpacked(path.join(path.dirname(require.resolve("@agentclientprotocol/claude-agent-acp/package.json")), "dist", "index.js")); } catch { return null; }
  }
  const set = path.join(home, "agents", "codex-acp", "node_modules", "@agentclientprotocol", "codex-acp", "dist", "index.js");
  return fs.existsSync(set) ? set : null;
}

/** A short plain name for a tool: "mcp__video-tool__set_caption_style" is "Set caption style". */
// Claude Code's own tools, in the words a person uses ("ToolSearch" was shown as is, 2026-11-22)
const OWN_WORDS = { ToolSearch: "Looking for the right tool", Read: "Reading a file", Write: "Writing a file", Edit: "Changing a file", MultiEdit: "Changing a file",
  Bash: "Running a command", PowerShell: "Running a command", Glob: "Finding files", Grep: "Searching files", LS: "Listing files", WebFetch: "Reading a web page",
  WebSearch: "Searching the web", TodoWrite: "Planning the steps", Task: "Starting a helper", Agent: "Starting a helper", NotebookEdit: "Changing a notebook" };
function humanTitle(name) {
  const raw = String(name || "").trim();
  if (OWN_WORDS[raw]) return OWN_WORDS[raw];
  const bare = raw.replace(/^mcp__[^_]+(?:-[^_]+)*__/, "").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim().toLowerCase();
  return bare ? bare[0].toUpperCase() + bare.slice(1) : "Working";
}
const toolName = (call) => String(call?._meta?.claudeCode?.toolName || call?.title || "");
const isOwnTool = (name) => name.startsWith(`mcp__${OWN_SERVER}__`);
const WHAT = { execute: "run a command", edit: "change a file", delete: "delete a file", move: "move a file", read: "read a file", search: "search your files", fetch: "fetch a web page" };

function killTree(proc) {
  if (!proc || proc.exitCode !== null || !proc.pid) return;
  try {
    if (process.platform === "win32") spawn("taskkill", ["/T", "/F", "/PID", String(proc.pid)], { windowsHide: true, stdio: "ignore" });
    else try { process.kill(-proc.pid, "SIGKILL"); } catch { proc.kill("SIGKILL"); }
  } catch { /* already gone */ }
}

function failure(e, who) {
  if (/was not found|not set up|Connect to a server/.test(String(e?.message))) return { kind: "login", message: String(e.message), raw: String(e.message) };
  const raw = `${e?.message || e} ${e?.data ? JSON.stringify(e.data) : ""}`;
  const kind = director.kindOf(raw, e?.status);
  const message = kind === "limit" ? `${who}'s usage limit is reached. Try again when it resets.`
    : kind === "login" ? `${who} is not signed in. Sign in, then try again.`
    : `${who} stopped before it finished. Try again.`;
  return { kind, message, raw: raw.slice(0, 600) };
}

class Session {
  constructor(o) {
    this.id = o.id; this.kind = o.kind; this.projectId = o.projectId; this.title = o.title || o.projectId; this.o = o;
    this.who = o.kind === "codex" ? "Codex" : "Claude Code";
    this.pending = new Map();            // permission requests waiting for the person
    this.always = new Set();             // tool names the person allowed for this chat
    this.stderr = [];
    this.running = null;
    this.closing = false;
    this.sessionId = "";
    this.caps = {};
  }

  emit(event) { try { this.o.emit(this.id, event); } catch { /* the window is gone */ } }

  async start({ resume, model } = {}) {
    const o = this.o;
    const entry = o.fake || adapterEntry(this.kind, o.home);
    if (!entry) throw new Error(`${this.who} is not set up on this computer yet.`);
    const cwd = path.join(o.home, "agents", this.projectId);
    fs.mkdirSync(cwd, { recursive: true });
    let cmd;
    if (this.kind === "claude" && !o.fake) cmd = require("./assistant-command").commandFor("claude");
    const env = director.cleanEnv({ ELECTRON_RUN_AS_NODE: "1", ...(cmd ? { CLAUDE_CODE_EXECUTABLE: [cmd.file, ...cmd.prefix][0] } : {}), ...(o.env || {}) });
    const proc = this.proc = spawn(process.execPath, [entry], { env, cwd, stdio: ["pipe", "pipe", "pipe"], windowsHide: true, detached: process.platform !== "win32" });
    proc.stderr.setEncoding("utf8");
    proc.stderr.on("data", (d) => { this.stderr.push(...String(d).split(/\r?\n/).filter(Boolean)); if (this.stderr.length > STDERR_LINES) this.stderr.splice(0, this.stderr.length - STDERR_LINES); });
    proc.on("error", (e) => this.emit({ type: "error", kind: "other", message: `${this.who} could not be started.` , raw: String(e.message) }));
    proc.on("exit", () => { if (!this.closing && this.running) this.emit({ type: "error", kind: "other", message: `${this.who} stopped unexpectedly. Try again.` }); });
    const acp = await loadSdk();
    const stream = acp.ndJsonStream(Writable.toWeb(proc.stdin), Readable.toWeb(proc.stdout));
    this.conn = new acp.ClientSideConnection(() => this.handler(), stream);
    const init = await this.conn.initialize({ protocolVersion: acp.PROTOCOL_VERSION, clientCapabilities: { fs: { readTextFile: false, writeTextFile: false }, terminal: false },
                                              clientInfo: { name: "ultimate-video-tool", version: o.version || "0" } });
    this.caps = init.agentCapabilities || {};
    const mcpServers = [{ name: OWN_SERVER, command: process.execPath, args: [o.bridge], env: [
      { name: "ELECTRON_RUN_AS_NODE", value: "1" }, { name: "VT_SERVER", value: o.server }, { name: "VT_TOKEN", value: o.key || "" }] }];
    const meta = this.kind === "claude" ? { systemPrompt: { append: instructions({ title: this.title, projectId: this.projectId }) },
      claudeCode: { options: { allowedTools: [`mcp__${OWN_SERVER}`, `mcp__${OWN_SERVER}__*`], allowDangerouslySkipPermissions: false, ...(model ? { model: director.modelName(model) } : {}) } } } : {};
    let note = "", resumed = false;
    if (resume && this.caps.sessionCapabilities?.resume) { await this.conn.resumeSession({ sessionId: resume, cwd, mcpServers, _meta: meta }); this.sessionId = resume; resumed = true; }
    else if (resume && this.caps.loadSession) { await this.conn.loadSession({ sessionId: resume, cwd, mcpServers, _meta: meta }); this.sessionId = resume; resumed = true; }
    else {
      const made = await this.conn.newSession({ cwd, mcpServers, _meta: meta });
      this.sessionId = made.sessionId;
      this.models = made.models || null;
      if (resume) note = "Started a new conversation (the earlier one could not be reopened).";
    }
    return { resumed, note, sessionId: this.sessionId, models: this.models ? { current: this.models.currentModelId, available: (this.models.availableModels || []).map((m) => ({ id: m.modelId, name: m.name })) } : null,
             images: !!this.caps.promptCapabilities?.image };
  }

  handler() {
    return {
      sessionUpdate: (n) => { this.update(n.update || {}); },
      requestPermission: (p) => this.permission(p),
    };
  }

  update(u) {
    if (u.sessionUpdate === "agent_message_chunk" && u.content?.type === "text") this.emit({ type: "text", text: u.content.text });
    else if (u.sessionUpdate === "tool_call" || u.sessionUpdate === "tool_call_update") {
      const name = toolName(u);
      this.emit({ type: "step", id: String(u.toolCallId || ""), title: u.title && !/^mcp__/.test(u.title) ? String(u.title).slice(0, 200) : humanTitle(name || u.title), tool: name || undefined,
                  status: u.status || (u.sessionUpdate === "tool_call" ? "in_progress" : "pending") });
    } else if (u.sessionUpdate === "plan") this.emit({ type: "plan", entries: (u.entries || []).map((e) => ({ text: String(e.content || "").slice(0, 200), status: e.status })) });
  }

  async permission(p) {
    const name = toolName(p.toolCall);
    const pick = (...kinds) => { for (const k of kinds) { const o = (p.options || []).find((x) => x.kind === k); if (o) return { outcome: { outcome: "selected", optionId: o.optionId } }; } return { outcome: { outcome: "cancelled" } }; };
    if (isOwnTool(name) || this.always.has(name)) return pick("allow_once", "allow_always");
    const requestId = crypto.randomBytes(8).toString("hex");
    const detail = p.toolCall?.rawInput ? JSON.stringify(p.toolCall.rawInput).slice(0, 2000) : "";
    const answer = await new Promise((resolve) => {
      const timer = setTimeout(() => { this.pending.delete(requestId); resolve("deny"); }, this.o.permissionTimeout || PERMISSION_TIMEOUT_MS);
      this.pending.set(requestId, (choice) => { clearTimeout(timer); this.pending.delete(requestId); resolve(choice); });
      this.emit({ type: "permission", requestId, tool: name, what: WHAT[p.toolCall?.kind] || "use a tool", title: String(p.toolCall?.title || name).slice(0, 300), detail });
    });
    if (answer === "chat") { this.always.add(name); return pick("allow_always", "allow_once"); }
    return answer === "once" ? pick("allow_once") : pick("reject_once", "reject_always");
  }

  answer(requestId, choice) {
    const resolve = this.pending.get(requestId);
    if (!resolve) throw new Error("That question is no longer waiting.");
    resolve(choice);
  }

  send(text, refs, images) {
    if (this.running) throw new Error(`${this.who} is still working on the last message.`);
    const prompt = [{ type: "text", text: toPrompt(text, refs) }];
    if (this.caps.promptCapabilities?.image) for (const im of images || []) prompt.push({ type: "image", mimeType: im.mime, data: im.data });
    this.title = this.title || text.slice(0, 60);
    this.running = this.conn.prompt({ sessionId: this.sessionId, prompt })
      .then((r) => this.emit({ type: "done", stopReason: r.stopReason }))
      .catch((e) => { const f = failure(e, this.who); this.o.log?.(`${this.who}: ${f.raw} | ${this.stderr.slice(-5).join(" / ")}`); this.emit({ type: "error", kind: f.kind, message: f.message }); })
      .finally(() => { this.running = null; for (const [, resolve] of this.pending) resolve("deny"); });
    return { ok: true };
  }

  async stop() {
    if (!this.running) return { ok: true };
    try { await this.conn.cancel({ sessionId: this.sessionId }); } catch { /* the agent may be gone */ }
    const done = await Promise.race([this.running.then(() => true), new Promise((r) => setTimeout(() => r(false), this.o.cancelGrace ?? CANCEL_GRACE_MS))]);
    if (!done) { killTree(this.proc); }
    return { ok: true, killed: !done };
  }

  close() { this.closing = true; for (const [, resolve] of this.pending) resolve("deny"); killTree(this.proc); }
}

/** The agents of one app window: opens conversations, keeps the list of them per video, and closes everything on exit. */
function createAgents(opts) {
  const sessions = new Map();
  const listFile = path.join(opts.home, "agents", "sessions.json");
  const readList = () => { try { return JSON.parse(fs.readFileSync(listFile, "utf8")); } catch { return {}; } };
  const writeList = (all) => { fs.mkdirSync(path.dirname(listFile), { recursive: true }); fs.writeFileSync(listFile, JSON.stringify(all, null, 1)); };
  const remember = (s) => {
    const all = readList(), mine = (all[s.projectId] || []).filter((x) => x.sessionId !== s.sessionId);
    mine.unshift({ sessionId: s.sessionId, agent: s.kind, title: s.title, at: new Date().toISOString() });
    all[s.projectId] = mine.slice(0, 20);
    writeList(all);
  };
  const get = (id) => sessions.get(V.id(id, "conversation")) || (() => { throw new Error("That conversation is not open."); })();

  return {
    status(kind) {
      V.kind(kind);
      if (kind === "claude") {
        const s = director.status();
        return { kind, found: !!s.found, logged_in: !!s.logged_in, version: s.version || "", reason: s.reason || "", adapter: !!adapterEntry("claude", opts.home) || !!opts.fake };
      }
      const adapter = !!adapterEntry("codex", opts.home);
      return { kind, found: adapter, logged_in: adapter, version: "", reason: adapter ? "" : "Codex is not set up in this app yet.", adapter };
    },
    async open(kind, projectId, o = {}) {
      V.kind(kind); V.id(projectId, "video");
      const server = opts.getServer();
      if (!server) throw new Error("Connect to a server first.");
      const id = crypto.randomBytes(8).toString("hex");
      const s = new Session({ id, kind, projectId, title: o.title, home: opts.home, version: opts.version, emit: opts.emit, log: opts.log, fake: opts.fake,
        bridge: opts.bridge, server: `${server}/mcp`, key: opts.getKey(server), env: opts.env, permissionTimeout: opts.permissionTimeout, cancelGrace: opts.cancelGrace });
      sessions.set(id, s);
      try {
        const r = await s.start({ resume: o.resume ? V.id(o.resume, "conversation") : "", model: o.model });
        remember(s);
        return { conversationId: id, ...r };
      } catch (e) {
        sessions.delete(id); s.close();
        throw new Error(failure(e, s.who).message);
      }
    },
    send(id, text, refs, images) { const s = get(id), r = s.send(V.text(text), V.refs(refs), V.images(images)); remember(s); return r; },
    stop(id) { return get(id).stop(); },
    permission(id, requestId, choice) { V.id(requestId, "question"); get(id).answer(requestId, V.choice(choice)); return { ok: true }; },
    /** Opens a window where the person signs in to the program (its own sign-in page); nothing from the window decides what is run. */
    signIn(kind) {
      V.kind(kind);
      if (kind !== "claude") throw new Error("Codex is not set up in this app yet.");
      if (process.platform !== "win32") throw new Error("Open a terminal and run: claude auth login");
      const c = require("./assistant-command").commandFor("claude");
      const file = [c.file, ...c.prefix][0];
      spawn("cmd.exe", ["/c", `start "Sign in to Claude Code" "${file}" auth login`], { windowsVerbatimArguments: true, detached: true, stdio: "ignore" }).unref();
      return { ok: true };
    },
    openInCode(projectId) {
      V.id(projectId, "video");
      const cwd = path.join(opts.home, "agents", projectId);
      fs.mkdirSync(cwd, { recursive: true });
      const local = process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, "Programs", "Microsoft VS Code", "bin", "code.cmd") : "";
      const exe = local && fs.existsSync(local) ? local : "code";
      try {
        const p = spawn("cmd.exe", ["/c", `"${exe}" "${cwd}"`], { windowsVerbatimArguments: true, detached: true, stdio: "ignore", windowsHide: true });
        p.on("error", () => {});
        p.unref();
      } catch (e) { throw new Error("VS Code could not be started. Install it from code.visualstudio.com."); }
      return { ok: true, folder: cwd };
    },
    list(projectId) { V.id(projectId, "video"); return readList()[projectId] || []; },
    close(id) { const s = sessions.get(id); if (s) { s.close(); sessions.delete(id); } },
    closeAll() { for (const s of sessions.values()) s.close(); sessions.clear(); },
    _sessions: sessions,
  };
}

module.exports = { createAgents, humanTitle, adapterEntry, killTree, failure };
