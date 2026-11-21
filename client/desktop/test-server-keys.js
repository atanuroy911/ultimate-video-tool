/* Keys of servers: kept privately, checked against the server, sent by the app's own connection and never by the page. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const K = require("./server-keys");
const { createTransport } = require("./transport");

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vt-keys-"));
  const file = path.join(dir, "keys.json");
  assert.equal(K.keyFor(file, "http://192.168.1.20:8790"), "", "no file, no key");
  K.saveKey(file, "http://192.168.1.20:8790", "abc123");
  K.saveKey(file, "http://10.0.0.5:8790", "other");
  assert.equal(K.keyFor(file, "http://192.168.1.20:8790"), "abc123");
  K.saveKey(file, "http://192.168.1.20:8790", "");
  assert.equal(K.keyFor(file, "http://192.168.1.20:8790"), "", "an empty key forgets it");
  assert.equal(K.keyFor(file, "http://10.0.0.5:8790"), "other", "the others stay");
  fs.writeFileSync(file, "not json");
  assert.equal(K.keyFor(file, "http://x"), "", "a damaged file counts as none");
  if (process.platform !== "win32") { K.saveKey(file, "http://a", "b"); assert.equal(fs.statSync(file).mode & 0o077, 0, "only this user can read it"); }

  assert.equal(K.clean("  abc  "), "abc");
  assert.throws(() => K.clean("two words"), /not a key/);
  assert.throws(() => K.clean("a".repeat(600)), /not a key/);

  // a server that wants "good" and says what it received
  const seen = [];
  const server = http.createServer((req, res) => {
    seen.push({ url: req.url, auth: req.headers.authorization || "" });
    const ok = req.headers.authorization === "Bearer good";
    res.writeHead(ok ? 200 : 401, { "Content-Type": "application/json" });
    res.end("{}");
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${server.address().port}`;
  try {
    assert.equal(await K.check(origin, "good"), "ok");
    assert.equal(await K.check(origin, "bad"), "refused");
    assert.equal(await K.check(origin, ""), "refused");
    assert.equal(await K.check("http://127.0.0.1:1", "good", 800), "unreachable");

    // the app's own connection adds the key to everything it forwards, and a page cannot choose another
    const dist = fs.mkdtempSync(path.join(os.tmpdir(), "vt-dist-"));
    fs.writeFileSync(path.join(dist, "index.html"), "<html></html>");
    const t = await createTransport({ server: origin, dist, key: "good" });
    seen.length = 0;
    const get = (headers) => new Promise((resolve, reject) => {
      http.get(t.origin + "/api/projects", { headers: { Cookie: `uvt_local_session=${t.secret}`, ...headers } }, (res) => { res.resume(); res.on("end", () => resolve(res.statusCode)); }).on("error", reject);
    });
    assert.equal(await get({}), 200);
    assert.equal(seen[0].auth, "Bearer good");
    assert.equal(await get({ Authorization: "Bearer page-chose-this" }), 200);
    assert.equal(seen[1].auth, "Bearer good", "the page cannot send another key");
    await t.close();
    const none = await createTransport({ server: origin, dist });
    seen.length = 0;
    assert.equal(await new Promise((resolve) => http.get(none.origin + "/api/projects", { headers: { Cookie: `uvt_local_session=${none.secret}` } }, (res) => { res.resume(); res.on("end", () => resolve(res.statusCode)); })), 401);
    assert.equal(seen[0].auth, "", "no key kept, none sent");
    await none.close();
    console.log("Server keys: kept privately, checked, sent by the app's own connection only.");
  } finally { server.close(); }
})().catch((e) => { console.error(e); process.exit(1); });
