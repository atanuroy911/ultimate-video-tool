/* The app's side of the helper: it starts one if none runs, reuses the one that does, replaces an older one, and talks to it. Real helper processes, plain Node. */
const assert = require("assert");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { WebSocketServer } = require("ws");
const control = require("./helper-control");

const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };
const wait = async (predicate, what, ms = 8000) => {
  const began = Date.now();
  while (Date.now() - began < ms) { if (await predicate()) return; await pause(40); }
  throw new Error("Timed out waiting for " + what);
};

(async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-control-"));
  const helperPath = path.join(__dirname, "helper.js");
  const upstream = http.createServer();
  const wss = new WebSocketServer({ server: upstream });
  let connections = 0;
  wss.on("connection", () => { connections++; });
  await new Promise((r) => upstream.listen(0, "127.0.0.1", r));
  const server = `http://127.0.0.1:${upstream.address().port}`;
  try {
    assert.equal(await control.status(home), null, "nothing runs yet");
    await assert.rejects(control.request(home, "GET", "/status"), /not running/);

    const first = await control.ensure({ home, helperPath });
    assert.equal(first.info.role, "helper");
    const pid = first.info.pid;
    assert.equal((await control.ensure({ home, helperPath })).info.pid, pid, "a helper that runs is reused, not started twice");

    await control.request(home, "POST", "/servers", { server });
    await wait(() => connections === 1, "the helper to reach the server");
    assert.equal((await control.request(home, "GET", "/status")).servers[0].connected, true);
    await assert.rejects(control.request(home, "POST", "/servers", { server: "ftp://nowhere" }), /address/i);

    // an older helper (left running by the previous version of the app) is stopped and replaced; the servers it knew are kept
    const replaced = await control.ensure({ home, helperPath, version: "0.0.1" });
    assert.notEqual(replaced.info.pid, pid, "a new helper");
    await wait(() => !alive(pid), "the old helper to exit");
    await wait(async () => (await control.request(home, "GET", "/status")).servers[0]?.connected === true, "the new helper to reach the saved server");
    assert.equal(connections, 2);

    // it keeps running when the one who started it is gone, and stops when told
    await control.request(home, "POST", "/stop", {});
    await wait(async () => (await control.status(home)) === null, "the helper to stop");
    assert(!fs.existsSync(path.join(home, "helper-run.json")));
    console.log("helper control: started once, reused, replaced when older, saved servers kept, stopped on request.");
  } finally {
    try { await control.request(home, "POST", "/stop", {}); } catch { /* already stopped */ }
    for (const s of wss.clients) s.terminate();
    wss.close();
    await new Promise((r) => upstream.close(r));
  }
})().catch((e) => { console.error(e); process.exit(1); });
