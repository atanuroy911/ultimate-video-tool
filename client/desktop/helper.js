/* The helper: the small program on this computer that keeps Claude and Codex ready for your Video Tool servers.
 * It starts with the computer and stays when the app is closed. It only calls out to each saved server (/ws), so firewalls and routers never matter.
 * No Python, models or project files live here. A server on the person's own network needs no key; for one outside it, the key is kept only in helper.json, readable by this user alone.
 * Run it as plain Node, or with the app's own program in Node mode (ELECTRON_RUN_AS_NODE=1, the way mcp-bridge.js runs).
 * VT_HELPER_HOME puts its files in another folder (then it is another helper, with its own device id), and VT_HELPER_NAME gives this computer another name on the server
 * (the lab bench runs a second helper this way, so the Server page lists it apart from the app's). */
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const WebSocket = require("ws");
const { serverURL } = require("./transport");
const { deviceId } = require("./device");

const KINDS = ["claude", "codex"];
const SLOTS = { direct: 1, ask: 2 };                    // one planning session at a time (it runs for minutes); two quick questions together
const REQUEST = /^[\w-]{1,64}$/;
const MAX_MESSAGE = 40 * 1024 * 1024;
const MAX_IMAGES = 12;
const WAIT_BEFORE_DROP = 120000;                        // a waiting task whose server has been gone this long is skipped: the server has given up on it
const KEEP_RESULT = 10 * 60000;                         // a finished answer that could not be delivered is offered again for this long

function homeDir(env = process.env, platform = process.platform) {
  if (env.VT_HELPER_HOME) return env.VT_HELPER_HOME;
  if (platform === "win32") return path.join(env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"), "Video Tool");
  if (platform === "darwin") return path.join(os.homedir(), "Library", "Application Support", "Video Tool");
  return path.join(env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config"), "Video Tool");
}

const readJson = (file, fallback) => { try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return fallback; } };
function writePrivate(file, data) {
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 1), { mode: 0o600 });
  fs.renameSync(tmp, file);
  try { fs.chmodSync(file, 0o600); } catch { /* Windows keeps this folder to its user already */ }
}

/** Ask a running helper (its port and key are in helper-run.json) something. Resolves {status, body}, or null when nothing answers. */
function call(run, method, route, body, wait = 1500) {
  return new Promise((resolve) => {
    if (!run || !run.port || !run.key) return resolve(null);
    const data = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = http.request({ host: "127.0.0.1", port: run.port, path: route, method, timeout: wait, headers: { Authorization: `Bearer ${run.key}`, ...(data ? { "Content-Type": "application/json", "Content-Length": data.length } : {}) } }, (res) => {
      let text = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { text += c; });
      res.on("end", () => { try { resolve({ status: res.statusCode, body: text ? JSON.parse(text) : {} }); } catch { resolve({ status: res.statusCode, body: {} }); } });
    });
    req.on("timeout", () => req.destroy());
    req.on("error", () => resolve(null));
    req.end(data);
  });
}

const friendly = (e) => {
  const m = String((e && e.message) || e || "");
  const code = /\b(401|403)\b/.exec(m);
  if (code) return "This server only accepts computers on its own network.";
  if (/ECONNREFUSED|ECONNRESET|EPIPE/.test(m)) return "The server is not answering.";
  if (/ENOTFOUND|EAI_AGAIN/.test(m)) return "The server's address was not found.";
  if (/ETIMEDOUT|timeout|EHOSTUNREACH|ENETUNREACH/i.test(m)) return "The server could not be reached.";
  return m.replace(/wss?:\/\/\S+/g, "the server").slice(0, 160);
};

class Helper {
  constructor({ home = homeDir(), device, runners, version, hostname = os.hostname(), backoff = [2000, 4000, 8000, 16000, 30000], checkEvery = 20000, quietAfter = 70000, watchEvery = 10000, logLimit = 1024 * 1024, onStop } = {}) {
    this.home = home;
    this.device = device;
    this.runners = runners || {};
    this.version = version || require("./package.json").version;
    this.hostname = hostname;
    this.backoff = backoff;
    this.checkEvery = checkEvery;
    this.quietAfter = quietAfter;
    this.watchEvery = watchEvery;
    this.onStop = onStop;
    this.logLimit = logLimit;
    this.key = crypto.randomBytes(32).toString("hex");
    this.files = { saved: path.join(home, "helper.json"), run: path.join(home, "helper-run.json"), log: path.join(home, "helper.log") };
    this.links = new Map();                             // server address -> its link
    this.assistants = {};                               // claude / codex: what the last check found
    this.queues = { direct: { running: 0, waiting: [] }, ask: { running: 0, waiting: [] } };
    this.jobs = new Map();                              // server|request -> the task, waiting or running
    this.started = new Date();
    this.stopped = false;
  }

  // ------------------------------------------------------------------ files and log
  log(message) {
    try {
      fs.mkdirSync(this.home, { recursive: true });
      if (fs.existsSync(this.files.log) && fs.statSync(this.files.log).size > this.logLimit) fs.renameSync(this.files.log, this.files.log + ".1");
      fs.appendFileSync(this.files.log, `[${new Date().toISOString()}] ${message}\n`);
    } catch { /* a log must never stop the helper */ }
  }

  save() {
    writePrivate(this.files.saved, { version: 1, servers: [...this.links.values()].map((l) => ({ server: l.server, ...(l.token ? { token: l.token } : {}) })) });
  }

  // ------------------------------------------------------------------ start and stop
  async start() {
    fs.mkdirSync(this.home, { recursive: true });
    this.device = this.device || deviceId(this.home);
    this.http = http.createServer((req, res) => this.handle(req, res));
    await new Promise((resolve, reject) => { this.http.once("error", reject); this.http.listen(0, "127.0.0.1", resolve); });
    this.port = this.http.address().port;
    const other = await this.claim();
    if (other) { await new Promise((r) => this.http.close(r)); this.http = null; return { already: true, run: other }; }
    this.log(`helper ${this.version} started (pid ${process.pid})`);
    for (const s of (readJson(this.files.saved, {}).servers || [])) {
      try { this.link(serverURL(s.server), String(s.token || "")); } catch (e) { this.log(`skipped a saved server: ${e.message}`); }
    }
    this.check().catch(() => {});
    this.timer = setInterval(() => this.check().then(() => this.announceAll()).catch(() => {}), this.checkEvery);
    this.watch = setInterval(() => this.watchLinks(), this.watchEvery);
    return this.info();
  }

  /** One helper per user: the run file names a helper that answers, or it is stale. Resolves the other helper's record, or null when this one now owns the file. */
  async claim() {
    const mine = { port: this.port, key: this.key, pid: process.pid, started: this.started.toISOString() };
    for (let attempt = 0; attempt < 4; attempt++) {
      try { fs.writeFileSync(this.files.run, JSON.stringify(mine), { flag: "wx", mode: 0o600 }); return null; } catch (e) { if (e.code !== "EEXIST") throw e; }
      let other = readJson(this.files.run, null);
      if (!other) { await new Promise((r) => setTimeout(r, 250)); other = readJson(this.files.run, null); }       // being written by a helper that started this instant
      const answer = other && await call(other, "GET", "/status");
      if (answer && answer.status === 200 && answer.body.role === "helper") return other;
      try { fs.rmSync(this.files.run, { force: true }); } catch { /* try again */ }
    }
    return readJson(this.files.run, { port: 0 });
  }

  async stop() {
    this.stopped = true;
    clearInterval(this.timer); clearInterval(this.watch);
    for (const job of this.jobs.values()) job.controller.abort();
    for (const link of this.links.values()) this.close(link);
    this.links.clear();
    if (readJson(this.files.run, {}).pid === process.pid) { try { fs.rmSync(this.files.run, { force: true }); } catch { /* the next helper removes it */ } }     // first: nobody may find a helper that is on its way out
    if (this.http) await new Promise((resolve) => { this.http.closeAllConnections?.(); this.http.close(resolve); });
    this.log("helper stopped");
  }

  // ------------------------------------------------------------------ the claude / codex check
  async check() {
    if (this.checking) return this.checking;
    this.checking = (async () => {
      await Promise.all(KINDS.map(async (kind) => {
        const runner = this.runners[kind];
        if (!runner) return;
        try { this.assistants[kind] = { ...(await (runner.statusAsync ? runner.statusAsync() : runner.status())), at: Date.now() }; } catch (e) { this.assistants[kind] = { found: false, logged_in: false, version: "", reason: e.message, at: Date.now() }; }
      }));
    })().finally(() => { this.checking = null; });
    return this.checking;
  }

  announce(link) {
    if (!link.sock || link.sock.readyState !== WebSocket.OPEN) return;
    for (const kind of KINDS) {
      const s = this.assistants[kind];
      if (s && s.found) this.send(link, { type: "director", director: kind, device_name: this.hostname, version: s.version, logged_in: !!s.logged_in });
    }
  }
  announceAll() { for (const link of this.links.values()) this.announce(link); }

  // ------------------------------------------------------------------ one link per server
  link(server, token) {
    const old = this.links.get(server);
    if (old) this.close(old);
    const link = { server, token, sock: null, state: "connecting", lastError: "", attempts: 0, since: null, lastSeen: 0, held: [], recent: new Map(), boot: "", timer: null };
    this.links.set(server, link);
    this.connect(link);
    return link;
  }

  close(link) {
    clearTimeout(link.timer);
    link.closed = true;
    for (const job of this.jobs.values()) if (job.link === link) job.controller.abort();
    try { link.sock && link.sock.terminate(); } catch { /* already gone */ }
  }

  connect(link) {
    if (this.stopped || link.closed) return;
    link.state = "connecting";
    const url = new URL("/ws", link.server);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    let sock;
    try { sock = new WebSocket(url, { headers: { "X-VT-Device": this.device, ...(link.token ? { Authorization: `Bearer ${link.token}` } : {}) }, handshakeTimeout: 15000, maxPayload: MAX_MESSAGE }); } catch (e) {
      link.lastError = friendly(e); link.state = "waiting";
      link.timer = setTimeout(() => this.connect(link), this.backoff[this.backoff.length - 1]);
      return;
    }
    link.sock = sock;
    const seen = () => { link.lastSeen = Date.now(); };
    sock.on("open", () => {
      link.state = "connected"; link.attempts = 0; link.lastError = ""; link.since = new Date().toISOString(); seen();
      this.log(`connected to ${link.server}`);
      this.announce(link);
      this.check().then(() => this.announce(link)).catch(() => {});
      this.flush(link);
    });
    sock.on("message", (raw) => { seen(); this.onMessage(link, raw); });
    sock.on("ping", seen);
    sock.on("pong", seen);
    sock.on("error", (e) => { link.lastError = friendly(e); });
    sock.on("close", () => {
      if (link.sock !== sock || link.closed) return;
      const was = link.state === "connected";
      link.state = "waiting"; link.since = null; link.droppedAt = Date.now();
      if (was) { this.log(`lost the connection to ${link.server}`); link.lastError = link.lastError || "The connection was lost."; }
      const wait = this.backoff[Math.min(link.attempts++, this.backoff.length - 1)];
      link.timer = setTimeout(() => this.connect(link), wait);
    });
  }

  /** A connection that went quiet (the computer slept, a router dropped it) is replaced: nothing is heard from a dead one, not even the server's pings. */
  watchLinks() {
    for (const link of this.links.values()) {
      if (link.state !== "connected" || !link.sock) continue;
      if (Date.now() - link.lastSeen > this.quietAfter) { link.lastError = "The connection went quiet."; link.sock.terminate(); }
      else { try { link.sock.ping(); } catch { /* closing */ } }
    }
  }

  send(link, message) {
    if (link.sock && link.sock.readyState === WebSocket.OPEN) { link.sock.send(JSON.stringify(message)); return true; }
    return false;
  }

  /** A finished answer goes back on the same link; when that link is down it is offered again as soon as it returns. */
  deliver(link, message) {
    if (this.send(link, message)) return;
    link.held.push({ at: Date.now(), message });
    link.held = link.held.slice(-20);
  }
  flush(link) {
    const held = link.held.filter((h) => Date.now() - h.at < KEEP_RESULT);
    link.held = [];
    for (const h of held) this.deliver(link, h.message);
  }

  // ------------------------------------------------------------------ tasks
  onMessage(link, raw) {
    let task;
    try { task = JSON.parse(String(raw)); } catch { return; }
    if (task && task.type === "hello") return this.hello(link, task);
    if (!task || typeof task !== "object" || !REQUEST.test(String(task.request || ""))) return;
    if (task.type === "cancel") return this.cancel(link, task.request);
    if (task.type !== "direct" && task.type !== "ask") return;
    const kind = KINDS.includes(task.assistant) ? task.assistant : "claude";
    const done = task.type === "direct" ? "director_done" : "ask_done";
    const refuse = (error, error_kind) => this.deliver(link, { type: done, request: task.request, ok: false, text: "", error, error_kind });
    if (typeof task.prompt !== "string" || !task.prompt) return refuse("The request had no prompt.", "other");
    if (task.type === "ask" && (!Array.isArray(task.images ?? []) || (task.images || []).length > MAX_IMAGES)) return refuse("Too many pictures were sent.", "other");
    this.forget(link);
    if (this.jobs.has(this.jobKey(link, task.request)) || link.recent.has(task.request)) return;       // the server asked again after a dropped connection: this one is being done, or was done and its answer is sent or held
    const job = { type: task.type, kind, link, request: task.request, project: String(task.project || ""), task, controller: new AbortController(), done };
    this.jobs.set(this.jobKey(link, task.request), job);
    this.queues[task.type].waiting.push(job);
    this.pump(task.type);
  }

  jobKey(link, request) { return `${link.server}|${request}`; }

  /** The first thing a server says. A different boot id than last time means the server restarted: nothing it was waiting for exists any more, so work for it stops. */
  hello(link, message) {
    const boot = typeof message.boot === "string" ? message.boot.slice(0, 40) : "";
    if (boot && link.boot && boot !== link.boot) {
      let dropped = 0;
      for (const job of this.jobs.values()) if (job.link === link) { job.controller.abort(); dropped++; }
      link.held = []; link.recent.clear();
      this.log(`${link.server} was restarted: stopped ${dropped} task(s) it was waiting for`);
    }
    if (boot) link.boot = boot;
  }

  /** Requests finished a while ago are forgotten. */
  forget(link) {
    for (const [request, at] of link.recent) if (Date.now() - at > KEEP_RESULT) link.recent.delete(request);
  }

  cancel(link, request) {
    const job = this.jobs.get(this.jobKey(link, request));
    if (job) { job.controller.abort(); this.log(`cancelled ${job.type} ${request}`); }
  }

  pump(type) {
    const q = this.queues[type];
    while (q.running < SLOTS[type] && q.waiting.length) {
      const job = q.waiting.shift();
      const gone = job.link.closed || (job.link.state !== "connected" && Date.now() - (job.link.droppedAt || Date.now()) > WAIT_BEFORE_DROP);
      if (job.controller.signal.aborted || gone) { this.jobs.delete(this.jobKey(job.link, job.request)); continue; }
      q.running++;
      const began = Date.now();
      this.perform(job).catch((e) => ({ ok: false, error: e.message, error_kind: "other" })).then((result) => {
        q.running--;
        this.jobs.delete(this.jobKey(job.link, job.request));
        job.link.recent.set(job.request, Date.now());
        this.log(`${job.type} ${job.request} ${result.ok ? "done" : "failed (" + (result.error_kind || "other") + ")"} in ${Math.round((Date.now() - began) / 100) / 10} s`);
        if (!job.controller.signal.aborted) this.deliver(job.link, this.answer(job, result));
        this.pump(type);
      });
    }
  }

  answer(job, r) {
    if (job.type === "direct") return { type: "director_done", request: job.request, ok: !!r.ok, error: String(r.error || "").slice(0, 500), error_kind: r.error_kind || "", exit_code: r.exit_code, model: r.model || "" };
    return { type: "ask_done", request: job.request, ok: !!r.ok, text: r.ok ? String(r.text || "") : "", error: String(r.error || "").slice(0, 500), error_kind: r.error_kind || "", models: r.models || [] };
  }

  async perform(job) {
    const runner = this.runners[job.kind];
    if (!this.assistants[job.kind] || Date.now() - (this.assistants[job.kind].at || 0) > 60000) { await this.check(); }
    const s = this.assistants[job.kind];
    const name = job.kind === "codex" ? "Codex" : "Claude";
    if (!runner || !s || !s.found) return { ok: false, error: `${name} is not installed on this computer.`, error_kind: "login" };
    if (!s.logged_in) return { ok: false, error: `${name} is not signed in on this computer. Open it once and sign in.`, error_kind: "login" };
    const t = job.task;
    if (job.type === "direct") {
      const onLog = (message) => this.send(job.link, { type: "director_log", request: job.request, project: job.project, message });
      return runner.run({ prompt: t.prompt, server: job.link.server, token: job.link.token, model: t.model, signal: job.controller.signal }, onLog);
    }
    return runner.ask({ system: String(t.system || ""), prompt: t.prompt, schema: t.schema, images: t.images || [], model: t.model, timeout: Number(t.timeout) || 300, signal: job.controller.signal });
  }

  // ------------------------------------------------------------------ what a person (or the app) can ask of it
  info() {
    const count = (type) => ({ running: this.queues[type].running, waiting: this.queues[type].waiting.length });
    return {
      role: "helper", version: this.version, pid: process.pid, started: this.started.toISOString(), ...this.memory(),
      servers: [...this.links.values()].map((l) => ({ server: l.server, connected: l.state === "connected", state: l.state, last_error: l.lastError, since: l.since })),
      assistants: Object.fromEntries(KINDS.filter((k) => this.runners[k]).map((k) => [k, this.assistants[k] ? { found: !!this.assistants[k].found, logged_in: !!this.assistants[k].logged_in, version: this.assistants[k].version || "", reason: this.assistants[k].reason || "" } : { found: false, logged_in: false, version: "", reason: "Checking…" }])),
      busy: this.queues.direct.running + this.queues.ask.running > 0, queue: { direct: count("direct"), ask: count("ask") },
    };
  }

  /** How much memory it holds, in MB: the process as a whole, and what the script itself keeps. */
  memory() {
    const m = process.memoryUsage();
    const mb = (n) => Math.round(n / 104857.6) / 10;
    return { rss_mb: mb(m.rss), heap_mb: mb(m.heapUsed), external_mb: mb(m.external) };
  }

  addServer(address, token) {
    const server = serverURL(address);
    if (token !== undefined && token !== null && token !== "" && (typeof token !== "string" || token.length > 512)) throw new Error("That key is not valid.");
    const key = token || "";                                              // only a server outside the person's own network asks for one
    const existing = this.links.get(server);
    if (existing && existing.token === key && !existing.closed) return this.info();
    this.link(server, key);
    this.save();
    return this.info();
  }

  removeServer(address) {
    const server = serverURL(address);
    const link = this.links.get(server);
    if (link) { this.close(link); this.links.delete(server); this.save(); }
    return this.info();
  }

  handle(req, res) {
    const send = (code, body) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(body)); };
    const expected = Buffer.from(`Bearer ${this.key}`), actual = Buffer.from(req.headers.authorization || "");
    if (expected.length !== actual.length || !crypto.timingSafeEqual(expected, actual)) { res.writeHead(401); return res.end(); }
    const route = `${req.method} ${String(req.url).split("?")[0]}`;
    let size = 0;
    const chunks = [];
    req.on("data", (c) => { size += c.length; if (size <= 64 * 1024) chunks.push(c); });
    req.on("end", async () => {
      if (size > 64 * 1024) return send(413, { error: "Too large." });
      let body = {};
      try { body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {}; } catch { return send(400, { error: "That was not JSON." }); }
      try {
        if (route === "GET /status") return send(200, this.info());
        if (route === "POST /servers") return send(200, this.addServer(body.server, body.token));
        if (route === "DELETE /servers") return send(200, this.removeServer(body.server));
        if (route === "POST /refresh") { await this.check(); this.announceAll(); return send(200, this.info()); }
        if (route === "POST /stop") { send(200, { stopping: true }); setTimeout(() => this.stop().then(() => this.onStop && this.onStop()), 50); return; }
        send(404, { error: "Unknown." });
      } catch (e) { send(400, { error: e.message }); }
    });
  }
}

async function main(argv) {
  const home = homeDir();
  const run = readJson(path.join(home, "helper-run.json"), null);
  if (argv.includes("--stop")) { const r = await call(run, "POST", "/stop", {}); console.log(r ? "stopping" : "not running"); return 0; }
  if (argv.includes("--status")) { const r = await call(run, "GET", "/status"); console.log(r ? JSON.stringify(r.body, null, 1) : "not running"); return r ? 0 : 1; }
  process.title = "Video Tool helper";
  const helper = new Helper({ home, hostname: process.env.VT_HELPER_NAME || undefined, runners: { claude: require("./director-runner"), codex: require("./codex-runner") }, onStop: () => process.exit(0) });
  const started = await helper.start();
  if (started.already) return 0;
  const quit = () => helper.stop().then(() => process.exit(0));
  process.on("SIGINT", quit);
  process.on("SIGTERM", quit);
  let crashes = 0;
  process.on("uncaughtException", (e) => { helper.log(`error: ${e && e.message}`); if (++crashes > 50) process.exit(1); });
  process.on("unhandledRejection", (e) => { helper.log(`error: ${e && e.message}`); });
  return null;
}

if (require.main === module) main(process.argv.slice(2)).then((code) => { if (code !== null) process.exit(code); }).catch((e) => { console.error(e.message); process.exit(1); });

module.exports = { Helper, homeDir, call, readJson };
