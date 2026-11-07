/* The helper, against fake servers and fake assistants: its local API needs the key, two servers connect, a restarted server is reconnected, tasks queue,
 * a cancelled one stops, a finished answer that could not be delivered is offered again, a second copy exits, and the log keeps no secrets.
 * The last part starts it as a real process and measures how much memory it uses while idle. */
const assert = require("assert");
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");
const { WebSocketServer } = require("ws");
const { Helper, call, readJson } = require("./helper");

const wait = async (predicate, what, ms = 5000) => {
  const began = Date.now();
  while (Date.now() - began < ms) { if (await predicate()) return; await new Promise((r) => setTimeout(r, 15)); }
  throw new Error("Timed out waiting for " + what);
};
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

function fakeServer(token) {
  const s = { token, messages: [], headers: [], devices: [], sockets: new Set(), connections: 0 };
  s.listen = async (port = 0) => {
    s.http = http.createServer();
    s.wss = new WebSocketServer({ server: s.http });
    s.wss.on("connection", (sock, req) => {
      s.connections++; s.headers.push(req.headers.authorization); s.devices.push(req.headers["x-vt-device"]); s.sockets.add(sock);
      sock.on("message", (raw) => s.messages.push(JSON.parse(String(raw))));
      sock.on("close", () => s.sockets.delete(sock));
    });
    await new Promise((r) => s.http.listen(port, "127.0.0.1", r));
    s.port = s.http.address().port; s.url = `http://127.0.0.1:${s.port}`;
  };
  s.send = (m) => { for (const sock of s.sockets) sock.send(JSON.stringify(m)); };
  s.drop = () => { for (const sock of s.sockets) sock.terminate(); };
  s.close = async () => { s.drop(); s.wss.close(); await new Promise((r) => s.http.close(r)); };
  s.got = (type, request) => s.messages.filter((m) => m.type === type && (request === undefined || m.request === request));
  return s;
}

function fakeAssistant(label) {
  const a = { label, running: 0, peak: 0, calls: [], held: false, waiting: [], logged_in: true, aborted: [] };
  a.statusAsync = async () => ({ found: true, logged_in: a.logged_in, version: label + "-1", reason: a.logged_in ? "" : "Open it and sign in." });
  a.hold = () => { a.held = true; };
  a.release = () => { a.held = false; for (const go of a.waiting.splice(0)) go(); };
  const work = async (kind, task, onLog) => {
    a.running++; a.peak = Math.max(a.peak, a.running); a.calls.push({ kind, task });
    try {
      onLog && onLog("a line of progress");
      if (a.held) await new Promise((go) => { a.waiting.push(go); task.signal.addEventListener("abort", go, { once: true }); });
      if (task.signal.aborted) { a.aborted.push(task.prompt); return { ok: false, error: "stopped", error_kind: "other" }; }
      return { ok: true };
    } finally { a.running--; }
  };
  a.run = async (task, onLog) => ({ error: "", exit_code: 0, model: "m", ...(await work("run", task, onLog)) });
  a.ask = async (task) => { const r = await work("ask", task); return r.ok ? { ok: true, text: JSON.stringify({ echo: task.prompt }), models: ["m"] } : r; };
  return a;
}

const tmp = (name) => fs.mkdtempSync(path.join(os.tmpdir(), name));

(async () => {
  const home = tmp("vt-helper-");
  const claude = fakeAssistant("claude"), codex = fakeAssistant("codex");
  const s1 = fakeServer("tok-one"), s2 = fakeServer("tok-two");
  await s1.listen(); await s2.listen();
  const options = { home, runners: { claude, codex }, hostname: "TEST-PC", backoff: [30, 60, 120], checkEvery: 150, quietAfter: 400, watchEvery: 60, logLimit: 4000 };
  let helper = new Helper({ ...options, onStop: () => { helper.stopped = true; } });
  try {
    const info = await helper.start();
    assert.equal(info.role, "helper");
    const run = readJson(path.join(home, "helper-run.json"));
    const status = (key) => fetch(`http://127.0.0.1:${run.port}/status`, { headers: key ? { Authorization: "Bearer " + key } : {} });
    const mine = (method, route, body) => call(run, method, route, body);

    // the local API needs the key
    assert.equal((await status()).status, 401);
    assert.equal((await status("not-the-key")).status, 401);
    assert.equal((await status(run.key)).status, 200);

    // two servers connect, each with its own key, and each hears about Claude and Codex
    await mine("POST", "/servers", { server: s1.url, token: "tok-one" });
    await mine("POST", "/servers", { server: s2.url, token: "tok-two" });
    await wait(() => s1.got("director").length >= 2 && s2.got("director").length >= 2, "both servers to hear the announcements");
    assert.deepEqual(s1.headers, ["Bearer tok-one"]); assert.deepEqual(s2.headers, ["Bearer tok-two"]);
    assert.deepEqual([...new Set(s1.got("director").map((m) => m.director))].sort(), ["claude", "codex"]);
    assert.equal(s1.got("director")[0].device_name, "TEST-PC");
    assert.equal(s1.got("director").find((m) => m.director === "claude").logged_in, true);
    let body = (await mine("GET", "/status")).body;
    assert.deepEqual(body.servers.map((x) => x.connected), [true, true]);
    assert(!JSON.stringify(body).includes("tok-one") && !JSON.stringify(body).includes("tok-two"), "no key in /status");
    assert.deepEqual(body.assistants.claude, { found: true, logged_in: true, version: "claude-1", reason: "" });
    const saved = path.join(home, "helper.json");
    assert.deepEqual(readJson(saved).servers.map((x) => x.token), ["tok-one", "tok-two"]);
    if (process.platform !== "win32") assert.equal(fs.statSync(saved).mode & 0o777, 0o600, "helper.json is for this user alone");

    // a server on the person's own network is added by its address alone: no key is sent or kept, and the computer names itself
    const s3 = fakeServer(""); await s3.listen();
    await mine("POST", "/servers", { server: s3.url });
    await wait(() => s3.got("director").length >= 2, "the keyless server to hear the announcements");
    assert.deepEqual(s3.headers, [undefined], "no Authorization header");
    assert.match(s3.devices[0], /^[0-9a-f]{8}$/);
    assert.equal(s3.devices[0], readJson(path.join(home, "device.json")).id, "the name is the one kept beside the app's files");
    assert.equal(s1.devices[0], s3.devices[0], "one computer, one name, whichever server it talks to");
    assert.deepEqual(readJson(saved).servers.find((x) => x.server === s3.url), { server: s3.url }, "nothing secret is saved for it");
    assert.equal((await mine("POST", "/servers", { server: s3.url, token: 5 })).status, 400);
    await mine("DELETE", "/servers", { server: s3.url });
    await s3.close();

    // a second copy for the same user exits and leaves the first alone
    const second = new Helper({ ...options });
    assert.equal((await second.start()).already, true);
    assert.equal((await mine("GET", "/status")).status, 200);

    // a restarted server is reconnected by itself
    const before = s1.connections;
    await s1.close();
    await wait(async () => (await mine("GET", "/status")).body.servers[0].connected === false, "the helper to notice the lost link");
    await wait(async () => /lost|not answering|could not be reached/.test((await mine("GET", "/status")).body.servers[0].last_error), "the reason to be shown");
    await s1.listen(s1.port);
    await wait(() => s1.connections > before, "the helper to reconnect");
    await wait(async () => (await mine("GET", "/status")).body.servers[0].connected, "the link to be reported up");

    // planning sessions run one at a time across servers; the others wait instead of being refused
    claude.hold();
    s1.send({ type: "direct", request: "d1", project: "p1", prompt: "plan one", assistant: "claude", model: "sonnet", director_token: "scoped-one" });
    await wait(() => claude.running === 1, "the first session to start");
    s2.send({ type: "direct", request: "d2", project: "p2", prompt: "plan two", assistant: "claude" });
    s1.send({ type: "direct", request: "d3", project: "p1", prompt: "plan three", assistant: "claude" });
    await wait(async () => (await mine("GET", "/status")).body.queue.direct.waiting === 2, "two sessions to wait");
    assert.equal(claude.running, 1);
    assert.equal(s1.got("director_done").length + s2.got("director_done").length, 0, "nobody was refused");
    assert.equal(claude.calls[0].task.model, "sonnet"); assert.equal(claude.calls[0].task.server, s1.url);
    assert.equal(claude.calls[0].task.token, ""); assert.equal(claude.calls[0].task.directorToken, "scoped-one", "a task receives only its project credential");
    assert(s1.got("director_log", "d1").length >= 1, "progress lines are passed on");
    claude.release();
    await wait(() => s1.got("director_done").length === 2 && s2.got("director_done").length === 1, "all three sessions to finish");
    assert.equal(claude.peak, 1);
    assert.deepEqual(s2.got("director_done").map((m) => m.request), ["d2"]);
    assert.deepEqual(s1.got("director_done").map((m) => m.request).sort(), ["d1", "d3"]);

    // questions run two at a time, with their pictures, and each answer returns to the server that asked
    codex.hold();
    const ask = (server, request, assistant) => server.send({ type: "ask", request, assistant, model: "sonnet", system: "Be brief.", prompt: "question " + request, schema: { type: "object" }, images: ["aGk="], timeout: 60 });
    ask(s1, "a1", "codex"); ask(s2, "a2", "codex"); ask(s1, "a3", "codex");
    await wait(() => codex.running === 2, "two questions to run together");
    await wait(async () => (await mine("GET", "/status")).body.queue.ask.waiting === 1, "the third question to wait");
    assert.deepEqual(codex.calls[0].task.images, ["aGk="]);
    codex.release();
    await wait(() => s1.got("ask_done").length === 2 && s2.got("ask_done").length === 1, "all three answers");
    assert.equal(codex.peak, 2);
    assert.deepEqual(JSON.parse(s2.got("ask_done", "a2")[0].text), { echo: "question a2" });
    assert.equal(s1.got("ask_done", "a1")[0].ok, true);

    // an assistant that is not signed in is told so at once, in plain words
    claude.logged_in = false;
    await mine("POST", "/refresh");
    s1.send({ type: "ask", request: "a4", assistant: "claude", prompt: "hello", schema: {}, images: [] });
    await wait(() => s1.got("ask_done", "a4").length === 1, "the refusal");
    assert.equal(s1.got("ask_done", "a4")[0].ok, false);
    assert.equal(s1.got("ask_done", "a4")[0].error_kind, "login");
    assert.match(s1.got("ask_done", "a4")[0].error, /not signed in/);
    claude.logged_in = true;
    await mine("POST", "/refresh");

    // a task the server gives up on is cancelled, and nothing is sent back for it
    claude.hold();
    s1.send({ type: "direct", request: "c1", project: "p1", prompt: "cancel me", assistant: "claude" });
    await wait(() => claude.running === 1, "the session to start");
    s1.send({ type: "cancel", request: "c1" });
    await wait(() => claude.aborted.includes("cancel me"), "the session to be stopped");
    await pause(120);
    assert.equal(s1.got("director_done", "c1").length, 0);
    claude.release();

    // an answer finished while the link was down is offered again when the link returns
    codex.hold();
    ask(s2, "h1", "codex");
    await wait(() => codex.running === 1, "the question to start");
    s2.drop();
    await wait(async () => (await mine("GET", "/status")).body.servers[1].connected === false, "the drop to be noticed");
    codex.release();
    await wait(() => s2.got("ask_done", "h1").length === 1, "the answer to arrive after the link returned");
    assert.equal(s2.got("ask_done", "h1")[0].ok, true);

    // a connection that went quiet is replaced
    const link = helper.links.get(s1.url), connections = s1.connections;
    await wait(() => { link.lastSeen = 0; return s1.connections > connections; }, "the quiet connection to be replaced");     // kept quiet until it is replaced: a pong could otherwise arrive in between

    // a task sent again after a dropped connection is not done twice: not while it runs, and not after it is finished
    const callsBefore = codex.calls.length;
    ask(s1, "dup1", "codex");
    await wait(() => s1.got("ask_done", "dup1").length === 1, "the first answer");
    ask(s1, "dup1", "codex");
    await pause(150);
    assert.equal(codex.calls.length, callsBefore + 1, "the same request was not run again");
    assert.equal(s1.got("ask_done", "dup1").length, 1);

    // a server that restarted is not waited for any more; the same server reconnecting is
    s1.send({ type: "hello", boot: "boot-one", jobs: [] });
    claude.hold();
    s1.send({ type: "direct", request: "r1", project: "p1", prompt: "work for the old server", assistant: "claude" });
    await wait(() => claude.running === 1, "the session to start");
    s1.send({ type: "hello", boot: "boot-one", jobs: [] });                                  // reconnected to the same server process
    await pause(120);
    assert.equal(claude.aborted.includes("work for the old server"), false, "the same server keeps its work");
    s1.send({ type: "hello", boot: "boot-two", jobs: [] });                                  // a new process: the old requests no longer exist
    await wait(() => claude.aborted.includes("work for the old server"), "the old server's work to be stopped");
    await pause(120);
    assert.equal(s1.got("director_done", "r1").length, 0, "nothing is sent back for it");
    claude.release();

    // a server can be taken away again
    await mine("DELETE", "/servers", { server: s2.url });
    await wait(() => s2.sockets.size === 0, "the link to close");
    assert.deepEqual((await mine("GET", "/status")).body.servers.map((x) => x.server), [s1.url]);
    assert.deepEqual(readJson(saved).servers.map((x) => x.token), ["tok-one"]);
    assert.equal((await mine("POST", "/servers", { server: "ftp://nowhere", token: "x" })).status, 400);

    // the log tells what happened and keeps no key, prompt or picture; it is cut when it grows
    for (let i = 0; i < 80; i++) helper.log("filler line to make the log grow past its limit");
    const log = fs.readFileSync(path.join(home, "helper.log"), "utf8") + (fs.existsSync(path.join(home, "helper.log.1")) ? fs.readFileSync(path.join(home, "helper.log.1"), "utf8") : "");
    assert(/connected to/.test(log) && /ask a1 done/.test(log));
    for (const secret of ["tok-one", "tok-two", "plan one", "question a1", "aGk=", "Be brief."]) assert(!log.includes(secret), "the log has " + secret);
    assert(fs.existsSync(path.join(home, "helper.log.1")), "the log was cut");
    assert(fs.statSync(path.join(home, "helper.log")).size < 4000 + 200);

    // a restarted helper remembers its servers
    await mine("POST", "/stop");
    await wait(() => helper.stopped && !fs.existsSync(path.join(home, "helper-run.json")), "the helper to stop and let go of its file");
    const connectionsBefore = s1.connections;
    helper = new Helper({ ...options });
    await helper.start();
    await wait(() => s1.connections > connectionsBefore, "the saved server to be reconnected");
    assert.equal(s1.headers[s1.headers.length - 1], "Bearer tok-one");
  } finally {
    await helper.stop(); await s1.close(); await s2.close();
  }

  // as a real process: one copy, and a small one while idle
  const realHome = tmp("vt-helper-real-");
  const quiet = fakeServer("tok-real"); await quiet.listen();
  const env = { ...process.env, VT_HELPER_HOME: realHome, VT_HELPER_NAME: "Lab PC (lab)", ELECTRON_RUN_AS_NODE: "1" };
  const first = spawn(process.execPath, [path.join(__dirname, "helper.js")], { env, stdio: "ignore" });
  try {
    const runFile = path.join(realHome, "helper-run.json");
    await wait(() => fs.existsSync(runFile), "the helper process to start", 15000);
    const run = readJson(runFile);
    assert.equal(run.pid, first.pid);
    await call(run, "POST", "/servers", { server: quiet.url, token: "tok-real" });
    await wait(async () => { const r = await call(run, "GET", "/status"); return r && r.body.servers[0].connected && r.body.assistants.claude && r.body.assistants.claude.reason !== "Checking…"; }, "the first check of Claude and Codex", 20000);
    await wait(() => quiet.got("director").length >= 1, "the server to hear the announcements");
    assert.equal(quiet.got("director")[0].device_name, "Lab PC (lab)", "the name from VT_HELPER_NAME is the name the server hears");
    const secondCopy = spawn(process.execPath, [path.join(__dirname, "helper.js")], { env, stdio: "ignore" });
    const code = await new Promise((resolve) => { const timer = setTimeout(() => { secondCopy.kill(); resolve("still running"); }, 10000); secondCopy.once("exit", (c) => { clearTimeout(timer); resolve(c); }); });
    assert.equal(code, 0, "a second copy exits at once");
    await pause(1500);
    const idle = (await call(run, "GET", "/status")).body.rss_mb;
    assert(idle < 80, `idle memory is ${idle} MB`);
    console.log(`helper: idle memory ${idle} MB (limit 80)`);
    await call(run, "POST", "/stop", {});
    await new Promise((resolve) => first.once("exit", resolve));
    assert(!fs.existsSync(runFile), "a stopped helper lets go of its run file");
  } finally { first.kill(); await quiet.close(); }
  console.log("helper: key required, two servers, reconnect, queues, cancel, held answers, one copy, remembered servers and a private log pass.");
})().catch((e) => { console.error(e); process.exit(1); });
